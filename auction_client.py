import sys
import argparse
import signal
import uuid
from tkinter import *
from tkinter import font
from tkinter import ttk
import msgpack
import zmq
from python_banyan.banyan_base import BanyanBase


class AuctionClient(BanyanBase):
    def __init__(self, **kwargs):
        super(AuctionClient, self).__init__(back_plane_ip_address=kwargs['back_plane_ip_address'],
                                            subscriber_port=kwargs['subscriber_port'],
                                            publisher_port=kwargs['publisher_port'],
                                            process_name=kwargs['process_name'],
                                            loop_time=kwargs['loop_time'])

        self.client_name = kwargs['process_name']
        self.client_id = None

        self.connected = False

        # Local auction information which is acquired by the Admin, but used by the local client for their own reference
        self.auction_state = 'WAITING'
        self.auction_items = {}

        self.set_subscriber_topic('auction_status')
        self.set_subscriber_topic('auction_items')
        self.set_subscriber_topic('auction_bids')
        self.set_subscriber_topic('auction_result')

        # GUI
        self.root = Tk()
        self.root.title("Auction Registration")
        self.root.geometry("300x200")
        self.root.resizable(False, False)
        self.content = ttk.Frame(self.root, borderwidth=5, relief="sunken", padding=12)
        self.content.pack(fill="both", expand=True)
        Label(self.content, text="Register your name").pack(anchor="center", pady=20)
        self.client_name = Entry(self.content, justify="center")
        self.client_name.pack(anchor="center", padx=30, pady=10, fill="x")
        Button(self.content, text="Enter", command=self.send).pack(anchor="center", padx=30, pady=10, fill="x")

        self.root.mainloop()

        try:
            self.receive_loop()
        except KeyboardInterrupt:
            self.clean_up()
            sys.exit(0)

    def send(self):
        self.publish_payload({'client_name': self.client_name.get()}, 'client_join')
        self.root.withdraw()

        self.auction = Toplevel(self.root)
        self.auction.title(f'Auction: {self.client_name.get()}')
        self.auction.geometry("400x600")

        self.bid_window = ttk.Frame(self.auction, borderwidth=5, relief="sunken")
        self.bid_window.grid(row=0, column=0, sticky="nsew")
        self.bid_header = ttk.Frame(self.bid_window)
        self.bid_header.pack(fill="x")
        Label(self.bid_header, text="Items bidding").pack(side="left")
        Button(self.bid_header, text="Bid", command=self.bid).pack(side="right")
        bidding_list = Listbox(self.bid_window, selectmode=EXTENDED)
        bidding_list.pack(fill="both", expand=True)


        self.sell_window = ttk.Frame(self.auction, borderwidth=5, relief="sunken")
        self.sell_window.grid(row=1, column=0, sticky="nsew")
        self.sell_header = ttk.Frame(self.sell_window)
        self.sell_header.pack(fill="x")
        Label(self.sell_header, text="Items you sell").pack(side="left")
        Button(self.sell_header, text="Sell", command=self.sell).pack(side="right")
        Listbox(self.sell_window, selectmode=EXTENDED).pack(fill="both", expand=True)

        self.auction_window = ttk.Frame(self.auction, borderwidth=5, relief="sunken")
        self.auction_window.grid(row=2, column=0, sticky="nsew")
        self.auction_header = ttk.Frame(self.auction_window)
        self.auction_header.pack(fill="x")
        Label(self.auction_header, text="Auction Event").pack(side="left")
        Label(self.auction_header, text="Time remaining [00:00:00]").pack(side="right")
        Listbox(self.auction_window, selectmode=EXTENDED).pack(fill="both", expand=True)

        self.auction.columnconfigure(0, weight=1)
        self.auction.rowconfigure(0, weight=3)
        self.auction.rowconfigure(1, weight=3)
        self.auction.rowconfigure(2, weight=3)

    def bid(self):
        self.bidding = Toplevel(self.root)
        self.bidding.title(f'{self.client_name.get()} is bidding...')
        self.bidding.geometry("300x200")
        self.bidding.resizable(False, False)

        self.bidding_window = ttk.Frame(self.bidding, borderwidth=5, relief="sunken", padding=12)
        self.bidding_window.pack(fill="both", expand=True)
        Label(self.bidding_window, text="Bid this item for").pack(anchor="center", pady=20)
        self.bid_amount = Entry(self.bidding_window, justify="center")
        self.bid_amount.pack(anchor="center", padx=30, pady=10, fill="x")
        Button(self.bidding_window, text="Bid item", command=self.process_bid).pack(anchor="center", padx=30, pady=10, fill="x")


    def sell(self):
        self.selling = Toplevel(self.root)
        self.selling.title(f'{self.client_name.get()} is selling...')
        self.selling.geometry("300x200")
        self.selling.resizable(False, False)

        self.selling_window = ttk.Frame(self.selling, borderwidth=5, relief="sunken")
        self.selling_window.pack(fill="both", expand=True)
        Label(self.selling_window, text="Sell an item").pack(anchor="center")
        self.item_name = Entry(self.selling_window, justify="center")
        self.item_name.pack(anchor="center", padx=30, pady=10, fill="x")
        Label(self.selling_window, text="Starting price:").pack(anchor="center")
        self.start_price = Entry(self.selling_window, justify="center")
        self.start_price.pack(anchor="center",pady=10)
        Button(self.selling_window, text="Sell item", command=self.process_sell).pack(anchor="center", padx=45, pady=10, fill="x")

    def process_bid(self):
        self.bidding.destroy()

    def process_sell(self):
        self.selling.destroy()










    def incoming_message_processing(self, topic, payload):
        if topic != 'auction_status' or not isinstance(payload, dict):
            return

        if payload.get('to') not in ('all_clients', self.client_name):
            return

        if not self.connected:
            self.connected = True
            print('Successfully connected to the auction server.')
        print(payload['message'])


def auction_client_cmdline():
    parser = argparse.ArgumentParser()

    parser.add_argument("-b", dest="back_plane_ip_address", default="None",
                        help="None or IP Address used by Backplane")

    parser.add_argument("-s", dest="subscriber_port", default='43125',
                        help="Port used by Subscriber")

    parser.add_argument("-p", dest="publisher_port", default='43124',
                        help="Port used by Publisher")

    # Creates a random four character name in case no name was manually inputted
    parser.add_argument("-n", dest="process_name",
                        default=f"Client-{uuid.uuid4().hex[:4]}",
                        help="Unique client name")

    parser.add_argument("-t", dest="loop_time", default=".1",
                        help="Time to run in seconds")

    args = parser.parse_args()

    if args.back_plane_ip_address == 'None':
        args.back_plane_ip_address = None

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