import sys
import argparse
import signal
import uuid
import ipaddress
from tkinter import *
from tkinter import font
from tkinter import ttk
import msgpack
import zmq
import threading
from tkinter import messagebox
from python_banyan.banyan_base import BanyanBase


class AuctionClient(BanyanBase):
    def __init__(self, **kwargs):

        self.subscriber_port = kwargs['subscriber_port']
        self.publisher_port = kwargs['publisher_port']
        self.process_name = kwargs['process_name']
        self.loop_time = kwargs['loop_time']

        self.client_name = self.process_name
        self.client_id = None

        self.connected = False

        self.auction_state = 'WAITING'
        self.remaining_time = 0
        self.auction_items = {}

        self.root = Tk()
        self.root.title("Auction Registration")
        self.root.geometry("300x280")
        self.root.resizable(False, False)
        self.content = ttk.Frame(self.root, borderwidth=5, relief="sunken", padding=12)
        self.content.pack(fill="both", expand=True)

        Label(self.content, text="Auction Admin / Backplane IP Address").pack(anchor="center", pady=5)
        self.backplane_ip = Entry(self.content, justify="center")
        self.backplane_ip.insert(0, kwargs['back_plane_ip_address'] or "")
        self.backplane_ip.pack(anchor="center", padx=30, pady=5, fill="x")

        Label(self.content, text="Register your name").pack(anchor="center", pady=10)
        self.client_name_entry = Entry(self.content, justify="center")
        self.client_name_entry.pack(anchor="center", padx=30, pady=5, fill="x")

        Button(self.content, text="Enter", command=self.send).pack(anchor="center", padx=30, pady=10, fill="x")

        self.root.mainloop()

    def send(self):
        backplane_ip = self.backplane_ip.get().strip()

        try:
            ipaddress.ip_address(backplane_ip)
        except ValueError:
            messagebox.showerror("Invalid IP Address", "Please enter a valid Auction Admin / Backplane IP address.")
            return

        client_name = self.client_name_entry.get().strip()

        if not client_name:
            messagebox.showerror("Invalid Name", "Please enter your client name.")
            return

        self.client_name = client_name

        try:
            super(AuctionClient, self).__init__(
                back_plane_ip_address=backplane_ip,
                subscriber_port=self.subscriber_port,
                publisher_port=self.publisher_port,
                process_name=self.process_name,
                loop_time=self.loop_time
            )

        except Exception as error:
            messagebox.showerror("Connection Error", f"Unable to connect to the Auction Backplane.\n\n{error}")
            return

        self.set_subscriber_topic('auction_status')
        self.set_subscriber_topic('auction_items')
        self.set_subscriber_topic('auction_bids')
        self.set_subscriber_topic('auction_results')

        self.publish_payload({'client_name': self.client_name}, 'client_join')

        self.root.withdraw()

        self.auction = Toplevel(self.root)
        self.auction.title(f'Auction: {self.client_name}')
        self.auction.geometry("400x600")

        self.bid_window = ttk.Frame(self.auction, borderwidth=5, relief="sunken")
        self.bid_window.grid(row=0, column=0, sticky="nsew")
        self.bid_header = ttk.Frame(self.bid_window)
        self.bid_header.pack(fill="x")
        Label(self.bid_header, text="Items bidding").pack(side="left")
        Button(self.bid_header, text="Bid", command=self.bid).pack(side="right")

        self.bid_scroll = ttk.Scrollbar(self.bid_window)
        self.bid_scroll.pack(side="right", fill="y")
        self.bid_display = Listbox(self.bid_window, yscrollcommand=self.bid_scroll.set)
        self.bid_display.pack(side="left", fill="both", expand=True)
        self.bid_scroll.config(command=self.bid_display.yview)

        self.sell_window = ttk.Frame(self.auction, borderwidth=5, relief="sunken")
        self.sell_window.grid(row=1, column=0, sticky="nsew")
        self.sell_header = ttk.Frame(self.sell_window)
        self.sell_header.pack(fill="x")
        Label(self.sell_header, text="Items you sell").pack(side="left")
        Button(self.sell_header, text="Sell", command=self.sell).pack(side="right")

        self.sell_scroll = ttk.Scrollbar(self.sell_window)
        self.sell_scroll.pack(side="right", fill="y")
        self.sell_display = Listbox(self.sell_window, yscrollcommand=self.sell_scroll.set)
        self.sell_display.pack(side="left", fill="both", expand=True)
        self.sell_scroll.config(command=self.sell_display.yview)

        self.auction_window = ttk.Frame(self.auction, borderwidth=5, relief="sunken")
        self.auction_window.grid(row=2, column=0, sticky="nsew")
        self.auction_header = ttk.Frame(self.auction_window)
        self.auction_header.pack(fill="x")
        Label(self.auction_header, text="Auction Event").pack(side="left")
        self.timer = Label(self.auction_header, text="Auction is yet to start")
        self.timer.pack(side="right")

        self.auction_scroll = ttk.Scrollbar(self.auction_window)
        self.auction_scroll.pack(side="right", fill="y")
        self.auction_display = Listbox(self.auction_window, yscrollcommand=self.auction_scroll.set)
        self.auction_display.pack(side="left", fill="both", expand=True)
        self.auction_scroll.config(command=self.auction_display.yview)

        self.auction.columnconfigure(0, weight=1)
        self.auction.rowconfigure(0, weight=3)
        self.auction.rowconfigure(1, weight=3)
        self.auction.rowconfigure(2, weight=3)

        threading.Thread(target=self.receive_loop, daemon=True).start()

    def bid(self):
        self.bidding = Toplevel(self.root)
        self.bidding.title(f'{self.client_name} is bidding...')
        self.bidding.geometry("300x200")
        self.bidding.resizable(False, False)

        self.bidding_window = ttk.Frame(self.bidding, borderwidth=5, relief="sunken", padding=12)
        self.bidding_window.pack(fill="both", expand=True)
        Label(self.bidding_window, text="Enter the ID of the item you want").pack(anchor="center")
        self.bid_ID = Entry(self.bidding_window, justify="center")
        self.bid_ID.pack(anchor="center", padx=30, pady=10)
        Label(self.bidding_window, text="Bid this item for").pack(anchor="center")
        self.bid_amount = Entry(self.bidding_window, justify="center")
        self.bid_amount.pack(anchor="center", padx=30, pady=10)
        Button(self.bidding_window, text="Bid item", command=self.process_bid).pack(anchor="center", padx=30, pady=10,
                                                                                    fill="x")

    def sell(self):
        self.selling = Toplevel(self.root)
        self.selling.title(f'{self.client_name} is selling...')
        self.selling.geometry("300x200")
        self.selling.resizable(False, False)

        self.selling_window = ttk.Frame(self.selling, borderwidth=5, relief="sunken")
        self.selling_window.pack(fill="both", expand=True)
        Label(self.selling_window, text="Sell an item").pack(anchor="center")
        self.item_name = Entry(self.selling_window, justify="center")
        self.item_name.pack(anchor="center", padx=30, pady=10, fill="x")
        Label(self.selling_window, text="Starting price:").pack(anchor="center")
        self.start_price = Entry(self.selling_window, justify="center")
        self.start_price.pack(anchor="center", pady=10)
        Button(self.selling_window, text="Sell item", command=self.process_sell).pack(anchor="center", padx=45, pady=10,
                                                                                      fill="x")

    def process_bid(self):
        self.place_bid(self.bid_ID.get(), self.bid_amount.get())
        self.bidding.destroy()

    def process_sell(self):
        self.submit_item(self.item_name.get(), self.start_price.get())
        self.selling.destroy()

    def incoming_message_processing(self, topic, payload):
        if not isinstance(payload, dict): return

        recipient = payload.get('to')

        if recipient not in ('all_clients', self.client_name): return

        event = payload.get('event')

        if topic == 'auction_status':
            if event == 'client_join':
                self.client_id = payload.get('client_id')
                self.connected = self.client_id is not None

                if self.connected:
                    self.auction_display.insert(END, 'You successfully joined the auction!')
                    self.auction_display.insert(END, f'Client Name: {self.client_name}')
                    self.auction_display.insert(END, f'Client ID: {self.client_id}')

            elif event == 'client_name_duplicate':
                self.connected = False
                messagebox.showerror("Registration Error", payload.get('message'))

            elif event == 'client_joined':
                self.auction_display.insert(END, f"{payload.get('client_name')} has joined the auction!")

            elif event == 'auction_sync':
                self.auction_state = payload.get('auction_state', 'WAITING')

            elif event == 'auction_started':
                self.auction_state = 'RUNNING'
                self.auction_display.insert(END, '\nTHE AUCTION HAS BEGUN!')

            elif event == 'timer_update':
                self.remaining_time = payload.get('remaining_time', 0)
                minutes = self.remaining_time // 60
                seconds = self.remaining_time % 60
                self.timer.config(text = f'Time remaining: {minutes:02d}:{seconds:02d}')

            elif event == 'auction_ended':
                self.auction_state = 'ENDED'
                self.auction_display.insert(END, '\nTHE AUCTION HAS ENDED!')

            elif event == 'item_rejected':
                messagebox.showwarning("Item Rejected", payload.get('message'))

            elif event == 'bid_rejected':
                messagebox.showwarning("Bid Rejected", payload.get('message'))

        elif topic == 'auction_items':
            if event == 'new_item':
                item = payload.get('item')

                if not isinstance(item, dict): return

                item_id = item.get('item_id')

                if not item_id: return

                self.auction_items[item_id] = item

                if item['seller_id'] == self.client_id:
                    self.sell_display.insert(END, '--------------------------------------------------')
                    self.sell_display.insert(END, f"Item ID: {item['item_id']}")
                    self.sell_display.insert(END, f"Item Name: {item['item_name']}")
                    self.sell_display.insert(END, f"Starting Price: {item['starting_price']}")
                else:
                    self.bid_display.insert(END, '\n--- NEW ITEM HAS BEEN PUT UP FOR AUCTION! ---')
                    self.bid_display.insert(END, f"Item ID: {item['item_id']}")
                    self.bid_display.insert(END, f"Item Name: {item['item_name']}")
                    self.bid_display.insert(END, f"Seller: {item['seller_name']}")
                    self.bid_display.insert(END, f"Starting Price: {item['starting_price']}")
                    self.bid_display.insert(END, '-----------------------------------------------')

        elif topic == 'auction_bids':
            if event == 'bid_accepted':
                item = payload.get('item')

                if not isinstance(item, dict): return

                item_id = item.get('item_id')

                if not item_id: return

                self.auction_items[item_id] = item

                self.auction_display.insert(END,'\n--- BID UPDATE ---')
                self.auction_display.insert(END,f"Item: {item['item_name']}")
                self.auction_display.insert(END,f"Bidder: {item['highest_bidder_name']}")
                self.auction_display.insert(END,f"Highest Bid: {item['highest_bid']:.2f}")
                self.auction_display.insert(END,'-------')

        elif topic == 'auction_results':
            if event == 'item_result':
                self.auction_display.insert(END, '\n--- AUCTION RESULTS ---')
                self.auction_display.insert(END, f"Item: {payload['item_name']}")

                if payload['winner_name'] is not None:
                    self.auction_display.insert(END, f"Winner: {payload['winner_name']}")
                    self.auction_display.insert(END, f"Winning Bid: {payload['winning_bid']:.2f}")
                else:
                    self.auction_display.insert(END, 'No bids were placed on this item.')

                self.auction_display.insert(END, '-------')

    def submit_item(self, item_name, starting_price):
        if not self.connected:
            print('You are not connected to the auction server.')
            return

        if self.auction_state not in ('WAITING', 'READY'):
            print('Auction is not accepting item submissions right now. Please wait.')
            return

        self.publish_payload(
            {
                'client_id': self.client_id,
                'item_name': item_name,
                'starting_price': starting_price
            },
            'item_submission'
        )

        print('Item submission sent to Admin.')

    def place_bid(self, item_id, bid_amount):
        if not self.connected:
            print('You are not connected to the auction server.')
            return

        if self.auction_state != 'RUNNING':
            print('The auction is not currently running. Please hold.')
            return

        if item_id not in self.auction_items:
            print('Item to bid not found. Please select an item within the item list.')
            return

        item = self.auction_items[item_id]

        if item['seller_id'] == self.client_id:
            print('You cannot bid on your own item!')
            return

        self.publish_payload(
            {
                'client_id': self.client_id,
                'item_id': item_id,
                'bid_amount': bid_amount
            },
            'bid_submission'
        )

        print('Bid submission sent to Admin.')


def auction_client_cmdline():
    parser = argparse.ArgumentParser()

    parser.add_argument("-b", dest="back_plane_ip_address", default=None,
                        help="IP Address used by Backplane")

    parser.add_argument("-s", dest="subscriber_port", default='43125',
                        help="Port used by Subscriber")

    parser.add_argument("-p", dest="publisher_port", default='43124',
                        help="Port used by Publisher")

    parser.add_argument("-n", dest="process_name",
                        default=f"Client-{uuid.uuid4().hex[:4]}",
                        help="Unique client name")

    parser.add_argument("-t", dest="loop_time", default=".1",
                        help="Time to run in seconds")

    args = parser.parse_args()

    AuctionClient(back_plane_ip_address=args.back_plane_ip_address,
                  subscriber_port=args.subscriber_port,
                  publisher_port=args.publisher_port,
                  process_name=args.process_name,
                  loop_time=float(args.loop_time))


def signal_handler(sig, frame):
    raise KeyboardInterrupt


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


if __name__ == '__main__':
    auction_client_cmdline()