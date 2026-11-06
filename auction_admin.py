import sys
import argparse
import signal
import uuid
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

        # Needed to determine whether the Auction ends and no one can input anything
        self.auction_state = 'WAITING'

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

    # Call this automatically for every message on a subscribed topic
    def incoming_message_processing(self, topic, payload):
        if not isinstance(payload, dict):
            return

        if topic == 'client_join':
            pass
        elif topic == 'item_submission':
            pass
        elif topic == 'bid_submission':
            pass

        # if topic == 'client_join' and isinstance(payload, dict) and 'client_name' in payload:
        #     client_name = payload['client_name']
        #     self.clients.add(client_name)
        #     print(f'{client_name} joined. Total clients: {len(self.clients)}')
        #
        #     self.publish_payload({'to': client_name, 'message': 'The auction is now open.'},
        #                          'auction_status')


    def broadcast_to_all(self, payload, topic):
        payload['to'] = 'all_clients'
        self.publish_payload(payload, topic)


    def register_client(self, payload):
        client_name = payload.get('client_name')

        if not isinstance(client_name, str) or not client_name.strip():
            return

        client_name = client_name.strip()

        # Prevent duplicate display names.
        for client in self.clients.values():
            if client['client_name'].casefold() == client_name.casefold():
                self.publish_payload(
                    {'to': client_name, 'event': 'client_name_duplicate','message': 'This name is already in use. Please choose another unique one.'},
                    'auction_status'
                )
                return

        # Generate a random client ID for the admin and client to pass around
        client_id = uuid.uuid4().hex

        self.clients[client_id] = { 'client_name': client_name }

        print(f'\n{client_name} has joined the auction.')
        print(f'Total clients: {len(self.clients)}')

        self.publish_payload(
            {'to': client_name, 'event': 'client_join', 'message': 'You have successfully joined the auction.', 'client_id': client_id},
            'auction_status'
        )

        # Broadcast to all clients a new client has joined
        self.broadcast_to_all(
            {'event': 'client_joined', 'client_name': client_name},
            'auction_status'
        )

        # Send items that have already been put up for auction to newly joined clients to catch up
        for item in self.auction_items.values():
            self.publish_payload(
                {'to': client_name, 'event': 'new_item', 'item': item
                },
                'auction_items'
            )


    def add_item(self, payload):
        if self.auction_state not in ('WAITING', 'READY'):
            return

        client_id = payload.get('client_id')

        if client_id not in self.clients:
            return

        item_name = payload.get('item_name')
        starting_price = payload.get('starting_price')

        if not isinstance(item_name, str) or not item_name.strip():
            return

        if isinstance(starting_price, bool):
            return

        try:
            starting_price = float(starting_price)
        except (ValueError, TypeError):
            return

        if starting_price < 0:
            return

        # Generate a random ID number for the item up to 8 characters
        # Needed for the client and admin to read back easily for each individual item
        item_id = uuid.uuid4().hex[:8].upper()

        # Initialize some starting information for the specific item
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
        print(f'Item ID: {item_id}')
        print(f'Item Name: {item['item_name']}')
        print(f'Seller: {item['seller_name']}')
        print(f'Starting Price: {starting_price:.2f}')
        print('-------')

        self.broadcast_to_all(
            {'event': 'new_item', 'item': item.copy()},
            'auction_items'
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