#!/usr/bin/python
import os
import time
import logging
import argparse
import transmissionrpc
from datetime import datetime


def get_disk_space(drive):
    d = os.statvfs(drive)
    # byte to gigabyte
    return int((d.f_bsize * d.f_bavail)/1073741824) #1000000000)

def main(args, logger):
    tc = transmissionrpc.Client(args.url,
                                args.port)
    
    today = datetime.now()
    delete = []
    torrents = sorted(tc.get_torrents(), key=lambda torrent: torrent.doneDate)

    for torrent in torrents:
        # calculate age of torrent
        done = datetime.utcfromtimestamp(torrent.doneDate)
        age = abs(today - done).days

        # only consider torrents which are seeding
        if torrent.status.lower() != 'seeding':
            logger.debug('{0} is not seeding'.format(torrent.name))
            continue

        # delete torrent if its above ratio treshold
        # and older than the minimum required age
        if torrent.ratio >= args.delete_ratio and age >= args.min_age:
            delete.append(torrent.id)
            logger.info('{0} with ratio {1} exceeded the delete ratio {2} and is more than {3} days old'.format(torrent.name,
                                                                                                                torrent.ratio,
                                                                                                                args.delete_ratio,
                                                                                                                args.min_age))
        # delete if torrent if its exhuasted the maximum age
        elif age >= args.max_age:
            delete.append(torrent.id)
            logger.info('{0} with ratio {1} is older than {2} days'.format(torrent.name, 
                                                                           torrent.ratio,
                                                                           args.max_age))
        # let know that no action has been taken
        else:
            logger.debug('{0} with ratio {1} which is {2} days old is not beeing deleted'.format(torrent.name,
                                                                                                 torrent.ratio,
                                                                                                 age))

        # remove the object from the list
        torrents.remove(torrent)
    
    if delete:
        print delete
        if not args.dryrun:
            tc.stop_torrent(delete)
            tc.remove_torrent(delete, delete_data=True)
        logger.debug('deleting {0} torrents with ids {1}'.format(len(delete), ', '.join(str(i) for i in sorted(delete))))

    disk_usage = get_disk_space(args.mountpoint)
    if disk_usage < args.mountpoint_treshold:
        logger.info('disk usage {0}GB is below the treshold of {1}GB'.format(disk_usage,
                                                                             args.mountpoint_treshold))

    while get_disk_space(args.mountpoint) < args.mountpoint_treshold and not args.dryrun:
        for torrent in torrents:
            if get_disk_space(args.mountpoint) >= args.mountpoint_treshold:
                break

            if torrent.status is 'seeding':
                logger.info('deleting {0} (disk usage {1}GB)'.format(torrent.name,
                                                                     get_disk_space(args.mountpoint)))

                # delete and remove torrent with data
                tc.stop_torrent(torrent.id)
                tc.remove_torrent(torrent.id, delete_data=True)

                # wait abit
                time.sleep(2)


if __name__ == "__main__":
    dir_path = os.path.dirname(os.path.realpath(__file__))

    # parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", help="Set loglevel to debug", action="store_true")
    parser.add_argument("-d", "--dryrun", help="Don't actully delete anyting", action="store_true")
    parser.add_argument("-u", "--url", help="Transmission URL", type=str, default="localhost")
    parser.add_argument("-p", "--port", help="Listening port of Transmission", type=int, default=9091)
    parser.add_argument("--min-age", help="Minimum required age of a torrent in days", type=int, default=2)
    parser.add_argument("--max-age", help="Delete when torrent has been seeded for this many days", type=int, default=90)
    parser.add_argument("--delete-ratio", help="Delete when torrent ratio goes ahove this", type=float, default=2.0)
    parser.add_argument("--mountpoint", help="Path to mountpoint for capacity check", type=str, default='/')
    parser.add_argument("--mountpoint-treshold", help="Delete files when below this trehold (in GB)", type=int, default=100)
    args = parser.parse_args()

    # set logging
    logger = logging.getLogger()
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    main(args, logger)
