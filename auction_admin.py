import sys
import argparse
import signal
import uuid
import time
import threading
from python_banyan.banyan_base import BanyanBase


class AuctionAdmin(BanyanBase):
    def __init__(self, **kwargs):
        super(AuctionAdmin, self).__init__(back_plane_ip_address=kwargs['back_plane_ip_address'],
                                           subscriber_port=kwargs['subscriber_port'],
                                           publisher_port=kwargs['publisher_port'],
                                           process_name=kwargs['process_name'],
                                           loop_time=kwargs['loop_time'])

        self.clients = {}
        self.auction_items = {}

        self.auction_state = 'WAITING'

        self.auction_duration = 0
        self.auction_end_time = None
        self.remaining_time = 0

        self.set_subscriber_topic('client_join')
        self.set_subscriber_topic('item_submission')
        self.set_subscriber_topic('bid_submission')

        self.publish_payload({'to': 'all_clients', 'message': 'The auction is now open.'},
                             'auction_status')
        print('The auction is now open. Waiting for clients...')

        try:
            self.receive_loop()
        except KeyboardInterrupt:
            self.clean_up()
            sys.exit(0)

    def incoming_message_processing(self, topic, payload):
        if not isinstance(payload, dict): return

        if topic == 'client_join':
            self.register_client(payload)
        elif topic == 'item_submission':
            self.add_item(payload)
        elif topic == 'bid_submission':
            self.add_bid(payload)


    def broadcast_to_all(self, payload, topic):
        payload['to'] = 'all_clients'
        self.publish_payload(payload, topic)


    def register_client(self, payload):
        client_name = payload.get('client_name')

        if not isinstance(client_name, str) or not client_name.strip(): return

        client_name = client_name.strip()

        for client in self.clients.values():
            if client['client_name'].casefold() == client_name.casefold():
                self.publish_payload(
                    {
                        'to': client_name,
                        'event': 'client_name_duplicate',
                        'message': 'This name is already in use. Please choose another unique one.'
                    },
                    'auction_status'
                )
                return

        client_id = uuid.uuid4().hex

        self.clients[client_id] = {'client_name': client_name}

        print(f'\n{client_name} has joined the auction.')
        print(f'Total clients: {len(self.clients)}')

        self.publish_payload(
            {
                'to': client_name,
                'event': 'client_join',
                'message': 'You have successfully joined the auction.',
                'client_id': client_id
            },
            'auction_status'
        )

        self.broadcast_to_all(
            {'event': 'client_joined', 'client_name': client_name},
            'auction_status'
        )

        self.publish_payload(
            {
                'to': client_name,
                'event': 'auction_sync',
                'auction_state': self.auction_state
            },
            'auction_status'
        )

        self.publish_payload(
            {
                'to': client_name,
                'event': 'timer_update',
                'remaining_time': self.remaining_time
            },
            'auction_status'
        )

        for item in self.auction_items.values():
            self.publish_payload(
                {'to': client_name, 'event': 'new_item', 'item': item.copy()},
                'auction_items'
            )


    def add_item(self, payload):
        if self.auction_state not in ('WAITING', 'READY'): return

        client_id = payload.get('client_id')

        if client_id not in self.clients: return

        item_name = payload.get('item_name')
        starting_price = payload.get('starting_price')

        if not isinstance(item_name, str) or not item_name.strip(): return

        if isinstance(starting_price, bool): return

        try:
            starting_price = float(starting_price)
        except (ValueError, TypeError):
            return

        if starting_price < 0: return

        item_id = uuid.uuid4().hex[:8].upper()

        item = {
            'item_id': item_id,
            'item_name': item_name.strip(),
            'seller_id': client_id,
            'seller_name': self.clients[client_id]['client_name'],
            'starting_price': starting_price,
            'highest_bid': starting_price,
            'highest_bidder_id': None,
            'highest_bidder_name': None
        }

        self.auction_items[item_id] = item

        print('\n--- NEW ITEM HAS BEEN PUT UP FOR AUCTION! ---')
        print(f"Item ID: {item_id}")
        print(f"Item Name: {item['item_name']}")
        print(f"Seller: {item['seller_name']}")
        print(f"Starting Price: {starting_price:.2f}")
        print('-------')

        self.broadcast_to_all(
            {'event': 'new_item', 'item': item.copy()},
            'auction_items'
        )


    def add_bid(self, payload):
        if self.auction_state != 'RUNNING': return

        client_id = payload.get('client_id')
        item_id = payload.get('item_id')
        bid_amount = payload.get('bid_amount')

        if client_id not in self.clients: return

        if item_id not in self.auction_items: return

        item = self.auction_items[item_id]

        if client_id == item['seller_id']:
            self.reject_bid(client_id, 'You cannot bid on your own item!')
            return

        if isinstance(bid_amount, bool): return

        try:
            bid_amount = float(bid_amount)
        except (ValueError, TypeError):
            return

        if bid_amount <= item['highest_bid']:
            self.reject_bid(client_id, 'Your bid must be greater than the current highest bid.')
            return

        item['highest_bid'] = bid_amount
        item['highest_bidder_id'] = client_id
        item['highest_bidder_name'] = self.clients[client_id]['client_name']

        print(
            f"\n{item['highest_bidder_name']} has placed a bid of {bid_amount:.2f} on {item['item_name']}."
        )

        self.broadcast_to_all(
            {
                'event': 'bid_accepted',
                'item': item.copy()
            },
            'auction_bids'
        )


    def reject_bid(self, client_id, message):
        client_name = self.clients[client_id]['client_name']

        self.publish_payload(
            {
                'to': client_name,
                'event': 'bid_rejected',
                'message': message
            },
            'auction_status'
        )

        print(f'\nBid rejected: {message}')


    def start_auction(self, duration):
        if self.auction_state != 'WAITING': return

        if not self.auction_items:
            print('Cannot start auction. No items available.')
            return

        if isinstance(duration, bool):
            return

        try:
            duration = int(duration)
        except (ValueError, TypeError):
            print('Invalid auction duration.')
            return

        if duration <= 0:
            print('Auction duration must be greater than zero.')
            return

        self.auction_duration = duration
        self.remaining_time = duration

        self.auction_state = 'RUNNING'

        self.auction_end_time = time.monotonic() + self.auction_duration

        print('\nTHE AUCTION HAS BEGUN!')

        self.broadcast_to_all(
            {
                'event': 'auction_started',
                'message': 'The auction has started!',
                'duration': self.auction_duration
            },
            'auction_status'
        )

        self.timer_thread = threading.Thread(target=self.auction_timer, daemon=True)
        self.timer_thread.start()


    def update_auction_timer(self):
        if self.auction_state != 'RUNNING': return

        self.remaining_time = max(0, int(self.auction_end_time - time.monotonic()))

        self.broadcast_to_all(
            {'event': 'timer_update', 'remaining_time': self.remaining_time},
            'auction_status'
        )

        if self.remaining_time <= 0:
            self.stop_auction()


    def auction_timer(self):
        while self.auction_state == 'RUNNING':
            self.update_auction_timer()
            time.sleep(1)


    def stop_auction(self):
        if self.auction_state not in ('WAITING', 'READY', 'RUNNING'): return

        self.auction_state = 'ENDED'

        print('\nTHE AUCTION HAS ENDED!')

        self.announce_results()

        self.broadcast_to_all(
            {
                'event': 'auction_ended',
                'message': 'The auction has concluded. Thank you attending the auction!'
            },
            'auction_status'
        )


    def announce_results(self):
        print('\n--- AUCTION RESULTS ---')

        for item in self.auction_items.values():
            print(f"\nItem: {item['item_name']}")

            if item['highest_bidder_id'] is not None:
                print(f"Winner: {item['highest_bidder_name']}")
                print(f"Winning Bid: {item['highest_bid']:.2f}")
            else:
                print('No bids received.')

            self.broadcast_to_all(
                {
                    'event': 'item_result',
                    'item_id': item['item_id'],
                    'item_name': item['item_name'],
                    'seller_name': item['seller_name'],
                    'winner_id': item['highest_bidder_id'],
                    'winner_name': item['highest_bidder_name'],
                    'winning_bid': (
                        item['highest_bid']
                        if item['highest_bidder_id'] is not None
                        else None
                    )
                },
                'auction_results'
            )


def auction_admin_cmdline():
    parser = argparse.ArgumentParser()

    parser.add_argument("-b", dest="back_plane_ip_address", default="None",
                        help="None or IP Address used by Backplane")

    parser.add_argument("-s", dest="subscriber_port", default='43124',
                        help="Port used by Subscriber")

    parser.add_argument("-p", dest="publisher_port", default='43125',
                        help="Port used by Publisher")

    parser.add_argument("-n", dest="process_name", default="AuctionAdmin",
                        help="Process name")

    parser.add_argument("-t", dest="loop_time", default=".1",
                        help="Time to run in seconds")

    args = parser.parse_args()

    if args.back_plane_ip_address == 'None':
        args.back_plane_ip_address = None

    AuctionAdmin(back_plane_ip_address=args.back_plane_ip_address,
                 subscriber_port=args.subscriber_port,
                 publisher_port=args.publisher_port,
                 process_name=args.process_name,
                 loop_time=float(args.loop_time))


def signal_handler(sig, frame):
    raise KeyboardInterrupt


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

if __name__ == '__main__':
    auction_admin_cmdline()