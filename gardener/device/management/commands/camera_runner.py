import cv2
import logging
import os
import time

from django.core.management import BaseCommand

from gardener.device.models import Camera

logger = logging.getLogger('gardener')


class Command(BaseCommand):
    help = 'Periodically start camera and capture snapshot (image/video).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--delay',
            type=int,
            required=False,
            default=900,
            help='Delay in seconds for periodical check.')

    def handle(self, *args, **options):
        default_delay = options['delay']
        while True:
            camera = Camera.objects.filter(device__is_active=True, is_active=True).first()
            if camera:
                capture(camera)
                delay = max(0, camera.snapshot_frequency - camera.snapshot_duration)
            else:
                delay = default_delay
            logger.debug(f'sleeping for {delay}s')
            time.sleep(delay)


def capture(camera):
    cap = cv2.VideoCapture(camera.index)
    if not cap.isOpened():
        logger.error(f'cannot open camera={camera.index}')
        return
    logger.info('opened cap')

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, camera.frame_width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, camera.frame_height)

    snapshot_number = camera.current_snapshot + 1
    if snapshot_number > camera.max_snapshots:
        snapshot_number = 1

    output_path = os.path.join(camera.snapshots_dir, f'{snapshot_number}.{camera.snapshot_extension}')
    if not os.path.isdir(camera.snapshots_dir):
        os.makedirs(camera.snapshots_dir)
    logger.info(f'output_path={output_path} - snapshot_number={snapshot_number}')

    fourcc = cv2.VideoWriter_fourcc(*'MJPG')
    fps = 24
    frame_size = (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    video_out = None
    if camera.snapshot_duration > 0:
        video_out = cv2.VideoWriter(output_path, fourcc, fps, frame_size)

    frames = 0
    while True:
        ret, frame = cap.read()
        if ret is True:
            if video_out is not None:
                video_out.write(frame)
                frames += 1
                if frames >= fps * camera.snapshot_duration:
                    break
            else:
                cv2.imwrite(output_path, frame)
                break
        else:
            break
    if not os.path.isfile(output_path):
        logger.error(f'failed to save snapshot - snapshot_number={snapshot_number} - output_path={output_path}')
    else:
        logger.info(f'output_path={output_path} - snapshot_number={snapshot_number} - frames={frames}')

    logger.info('releasing cap')
    cap.release()
    if video_out is not None:
        video_out.release()
    logger.info('released cap')

    camera.current_snapshot = snapshot_number
    camera.save()
