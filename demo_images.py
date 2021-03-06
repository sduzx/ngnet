#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Author: Nghia Tran
# Edited from demo.py


"""
Detects Cars in an video using KittiBox.

Input: Video
Output: Video (with Cars plotted in Green)

Utilizes: Trained KittiBox weights. If no logdir is given,
pretrained weights will be downloaded and used.

Usage:
python demo_video.py --input_image data/demo.png [--output_image output_image]
                [--logdir /path/to/weights] [--gpus 0]


"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import logging
import os
import sys
import imageio

# configure logging

logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s',
                    level=logging.INFO,
                    stream=sys.stdout)

# https://github.com/tensorflow/tensorflow/issues/2034#issuecomment-220820070
import numpy as np
import scipy as scp
import scipy.misc
import tensorflow as tf
import time
import cv2
import argparse

sys.path.insert(1, 'incl')
from utils import train_utils as kittibox_utils

try:
    # Check whether setup was done correctly
    import tensorvision.utils as tv_utils
    import tensorvision.core as core
except ImportError:
    # You forgot to initialize submodules
    logging.error("Could not import the submodules.")
    logging.error("Please execute:"
                  "'git submodule update --init --recursive'")
    exit(1)


parser = argparse.ArgumentParser(description='Create summsion for Kitti')
parser.add_argument('image_dir', type=str, help='Path to video.')
parser.add_argument('logdir', type=str, help='Path to logdir.')
parser.add_argument('--save', '-s', type=str, default='', help='Save file.')
parser.add_argument('--limit', '-l', type=int, default=-1, help='Save file.')
parser.add_argument('--framerate', '-f', type=int, default=10, help='Save file.')

def main():
    args = parser.parse_args()
    tv_utils.set_gpus_to_use()
    logdir = args.logdir

    # Loading hyperparameters from logdir
    hypes = tv_utils.load_hypes_from_logdir(logdir, base_path='hypes')

    logging.info("Hypes loaded successfully.")

    # Loading tv modules (encoder.py, decoder.py, eval.py) from logdir
    modules = tv_utils.load_modules_from_logdir(logdir)
    logging.info("Modules loaded successfully. Starting to build tf graph.")

    # Create tf graph and build module.
    with tf.Graph().as_default():
        # Create placeholder for input
        image_pl = tf.placeholder(tf.float32, shape=(hypes["image_height"], hypes["image_width"], 3))
        image = tf.expand_dims(image_pl, 0)
        # build Tensorflow graph using the model from logdir
        prediction = core.build_inference_graph(hypes, modules,
                                                image=image)

        logging.info("Graph build successfully.")

        # Create a session for running Ops on the Graph.
        sess = tf.Session()
        saver = tf.train.Saver()

        # Load weights from logdir
        core.load_weights(logdir, sess, saver)

        logging.info("Weights loaded successfully.")

    if args.save:
        save_file = args.save
    else:
        save_file = 'video.mp4'

    if os.path.isfile(save_file):
        os.remove(save_file)

    # Get all images to make video
    image_names =  sorted(os.listdir(args.image_dir))[:args.limit]

    if len(image_names) == 0:
        logging.error("No image found in given image_dir.")
        exit(1)

    start = time.time()

    if os.path.isfile(save_file):
        os.remove(save_file)

    logging.info("Making video")
    with imageio.get_writer(save_file, mode='I', fps=args.framerate) as writer:
        for i, image_name in enumerate(image_names):
            input_image = os.path.join(args.image_dir, image_name)
            # logging.info("Starting inference using %s as input %d/%d" % (input_image, i, len(image_names)))

            # Load and resize input image
            oimage = scp.misc.imread(input_image)

            oshape = oimage.shape[:2]
            rh = oshape[0] / float(hypes["image_height"])
            rw = oshape[1] / float(hypes["image_width"])

            image = scp.misc.imresize(oimage, (hypes["image_height"],
                                              hypes["image_width"]),
                                      interp='cubic')
            feed = {image_pl: image}

            # Run KittiBox model on image
            pred_boxes = prediction['pred_boxes_new']
            pred_confidences = prediction['pred_confidences']
            (np_pred_boxes, np_pred_confidences) = sess.run([pred_boxes,
                                                             pred_confidences],
                                                            feed_dict=feed)

            # np_pred_boxes[:, :, 0] *= rw
            # np_pred_boxes[:, :, 2] *= rw
            # np_pred_boxes[:, :, 1] *= rh
            # np_pred_boxes[:, :, 3] *= rh

            # Apply non-maximal suppression
            # and draw predictions on the image
            threshold = 0.5
            output_image, rectangles = kittibox_utils.add_rectangles(
                hypes, [image], np_pred_confidences,
                np_pred_boxes, show_removed=False,
                use_stitching=True, rnn_len=1,
                min_conf=threshold, tau=hypes['tau'], color_acc=(0, 255, 0))

            output_image = scp.misc.imresize(output_image, oshape, interp='cubic')
            writer.append_data(output_image)

    time_taken = time.time() - start
    logging.info('Video saved as %s' % save_file)
    logging.info('Number of images: %d' % len(image_names))
    logging.info('Time takes: %.2f s' % (time_taken))
    logging.info('Frequency: %.2f fps' % (len(image_names) / time_taken))

if __name__ == '__main__':
    main()

