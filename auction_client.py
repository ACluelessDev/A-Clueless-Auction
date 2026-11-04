import sys
from python_banyan.banyan_base import BanyanBase
import argparse
import signal

class AuctionClient(BanyanBase):
    def __init__(self, **kwargs):
        super(AuctionClient, self).__init__(back_plane_ip_address=kwargs['back_plane_ip_address'],
                                            subscriber_port=kwargs['subscriber_port'],
                                            publisher_port=kwargs['publisher_port'],
                                            process_name=kwargs['process_name'],
                                            loop_time=kwargs['loop_time'])

        self.set_subscriber_topic('send_bid')
        self.set_subscriber_topic('send_sell')

        self.bidder_message = kwargs['Bidded.']
        self.seller_message = kwargs['Sold.']

        self.publish_payload({'Bidding received: ': self.bidder_message}, 'receive_bid')
        self.publish_payload({'Selling received: ': self.seller_message}, 'receive_sell')

        try:
            self.receive_loop()
        except KeyboardInterrupt:
            self.clean_up()
            sys.exit(0)

def auction_client_cmdline():
    parser = argparse.ArgumentParser()

    parser.add_argument("-b", dest="back_plane_ip_address", default="None",
                        help="None or IP Address used by Backplane")

    parser.add_argument("-s", dest="subscriber_port", default='8000',
                        help="Port used by Subscriber")

    parser.add_argument("-p", dest="publisher_port", default='7000',
                        help="Port used by Publisher")

    parser.add_argument("-m", dest="number_of_messages", default="10",
                        help="Number of messages to send")

    parser.add_argument("-n", dest="process_name", default="EchoCMDClient",
                        help="Process name")

    parser.add_argument("-t", dest="loop_time", default=".1",
                        help="Time to run in seconds")

    args = parser.parse_args()

    if args.back_plane_ip_address == 'None':
        args.back_plane_ip_address = None

    kw_options = {'back_plane_ip_address': args.back_plane_ip_address,
                  'subscriber_port': args.subscriber_port,
                  'publisher_port': args.publisher_port,
                  'number_of_messages': int(args.number_of_messages),
                  'process_name': args.process_name,
                  'loop_time': float(args.loop_time)}

    AuctionClient(**kw_options)

def signal_handler(sig, frame):
    raise KeyboardInterrupt

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

if __name__ == '__main__':
    auction_client_cmdline()