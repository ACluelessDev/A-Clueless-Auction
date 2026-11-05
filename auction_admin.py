import sys
import argparse
import signal
from python_banyan.banyan_base import BanyanBase


class AuctionAdmin(BanyanBase):
    def __init__(self, **kwargs):
        super(AuctionAdmin, self).__init__(back_plane_ip_address=kwargs['back_plane_ip_address'],
                                           subscriber_port=kwargs['subscriber_port'],
                                           publisher_port=kwargs['publisher_port'],
                                           process_name=kwargs['process_name'],
                                           loop_time=kwargs['loop_time'])

        self.clients = set() # For multiple clients to join
        self.set_subscriber_topic('client_join')

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
        if topic == 'client_join' and isinstance(payload, dict) and 'client_name' in payload:
            client_name = payload['client_name']
            self.clients.add(client_name)
            print(f'{client_name} joined. Total clients: {len(self.clients)}')

            self.publish_payload({'to': client_name, 'message': 'The auction is now open.'},
                                 'auction_status')


def auction_admin_cmdline():
    parser = argparse.ArgumentParser()

    parser.add_argument("-b", dest="back_plane_ip_address", default="None",
                        help="None or IP Address used by Backplane")

    parser.add_argument("-s", dest="subscriber_port", default='8000',
                        help="Port used by Subscriber")

    parser.add_argument("-p", dest="publisher_port", default='7000',
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