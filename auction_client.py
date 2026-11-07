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

        # Local auction information which is acquired by the Admin, but used by the local client for their own reference
        self.auction_state = 'WAITING'
        self.auction_items = {}

        self.set_subscriber_topic('auction_status')
        self.set_subscriber_topic('auction_items')
        self.set_subscriber_topic('auction_bids')
        self.set_subscriber_topic('auction_result')

        # Tell the Admin we exist
        self.publish_payload({'client_name': self.client_name}, 'client_join')
        print(f'{self.client_name}: contacting the auction server...')

        try:
            self.receive_loop()
        except KeyboardInterrupt:
            self.clean_up()
            sys.exit(0)


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

    parser.add_argument("-s", dest="subscriber_port", default='43124',
                        help="Port used by Subscriber")

    parser.add_argument("-p", dest="publisher_port", default='43125',
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