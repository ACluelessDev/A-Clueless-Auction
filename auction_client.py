import sys
import argparse
import signal
import uuid
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

        self.auction_state = 'WAITING'
        self.remaining_time = 0
        self.auction_items = {}

        self.set_subscriber_topic('auction_status')
        self.set_subscriber_topic('auction_items')
        self.set_subscriber_topic('auction_bids')
        self.set_subscriber_topic('auction_results')

        self.publish_payload({'client_name': self.client_name}, 'client_join')
        print(f'{self.client_name}: contacting the auction server...')

        try:
            self.receive_loop()
        except KeyboardInterrupt:
            self.clean_up()
            sys.exit(0)


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
                    print('Successfully joined the auction!')
                    print(f'Client Name: {self.client_name}')
                    print(f'Client ID: {self.client_id}')

            elif event == 'client_name_duplicate':
                self.connected = False
                print(f"\n{payload.get('message')}")
            elif event == 'client_joined':
                print(f"\n{payload.get('client_name')} has joined the auction!")
            elif event == 'auction_sync':
                self.auction_state = payload.get('auction_state', 'WAITING')
            elif event == 'auction_started':
                self.auction_state = 'RUNNING'
                print('\nTHE AUCTION HAS BEGUN!')
            elif event == 'timer_update':
                self.remaining_time = payload.get('remaining_time', 0)
                minutes = self.remaining_time // 60
                seconds = self.remaining_time % 60
                print(f'Time remaining: {minutes:02d}:{seconds:02d}')
            elif event == 'auction_ended':
                self.auction_state = 'ENDED'
                print('\nTHE AUCTION HAS ENDED!')
            elif event == 'item_rejeted':
                print(f"\nYour item submission was rejected: {payload.get('message')}")
            elif event == 'bid_rejected':
                print(f"\nYour bid was rejected: {payload.get('message')}")

        elif topic == 'auction_items':
            if event == 'new_item':
                item = payload.get('item')

                if not isinstance(item, dict): return

                item_id = item.get('item_id')

                if not item_id: return

                self.auction_items[item_id] = item

                print('\n--- NEW ITEM HAS BEEN PUT UP FOR AUCTION! ---')
                print(f"Item ID: {item['item_id']}")
                print(f"Item Name: {item['item_name']}")
                print(f"Seller: {item['seller_name']}")
                print(f"Starting Price: {item['starting_price']}")
                print('-------')

        elif topic == 'auction_bids':
            if event == 'bid_accepted':
                item = payload.get('item')

                if not isinstance(item, dict): return

                item_id = item.get('item_id')

                if not item_id: return

                self.auction_items[item_id] = item

                print('\n--- BID UPDATE ---')
                print(f"Item: {item['item_name']}")
                print(f"Bidder: {item['highest_bidder_name']}")
                print(f"Highest Bid: {item['highest_bid']:.2f}")
                print('-------')

        elif topic == 'auction_results':
            if event == 'item_result':
                print('\n--- AUCTION RESULTS ---')
                print(f"Item: {payload['item_name']}")

                if payload['winner_name'] is not None:
                    print(f"Winner: {payload['winner_name']}")
                    print(f"Winning Bid: {payload['winning_bid']:.2f}")
                else:
                    print('No bids were placed on this item.')

                print('-------')


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

    parser.add_argument("-b", dest="back_plane_ip_address", default="None",
                        help="None or IP Address used by Backplane")

    parser.add_argument("-s", dest="subscriber_port", default='43124',
                        help="Port used by Subscriber")

    parser.add_argument("-p", dest="publisher_port", default='43125',
                        help="Port used by Publisher")

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