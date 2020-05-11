# encoding: utf-8
"""
@author:  xingyu liao
@contact: liaoxingyu5@jd.com
"""

import argparse
import logging
import tqdm
import sys

import numpy as np
import torch
from torch.backends import cudnn

sys.path.append('.')

from fastreid.evaluation import evaluate_rank
from fastreid.config import get_cfg
from fastreid.utils.logger import setup_logger
from fastreid.data import build_reid_test_loader
from predictor import FeatureExtractionDemo
from fastreid.utils.visualizer import Visualizer

cudnn.benchmark = True
logger = logging.getLogger('fastreid')


def setup_cfg(args):
    # load config from file and command-line arguments
    cfg = get_cfg()
    cfg.merge_from_file(args.config_file)
    cfg.merge_from_list(args.opts)
    cfg.freeze()
    return cfg


def get_parser():
    parser = argparse.ArgumentParser(description="Feature extraction with reid models")
    parser.add_argument(
        "--config-file",
        metavar="FILE",
        help="path to config file",
    )
    parser.add_argument(
        '--device',
        default='cuda: 1',
        help='CUDA device to use'
    )
    parser.add_argument(
        '--parallel',
        action='store_true',
        help='if use multiprocess for feature extraction.'
    )
    parser.add_argument(
        "--dataset-name",
        help="a test dataset name for visualizing ranking list."
    )
    parser.add_argument(
        "--output",
        default="./vis_rank_list",
        help="a file or directory to save rankling list result.",

    )
    parser.add_argument(
        "--num-vis",
        default=100,
        help="number of query images to be visualized",
    )
    parser.add_argument(
        "--rank-sort",
        default="ascending",
        help="rank order of visualization images by AP metric",
    )
    parser.add_argument(
        "--max-rank",
        default=10,
        help="maximum number of rank list to be visualized",
    )
    parser.add_argument(
        "--opts",
        help="Modify config options using the command-line 'KEY VALUE' pairs",
        default=[],
        nargs=argparse.REMAINDER,
    )
    return parser


if __name__ == '__main__':
    args = get_parser().parse_args()
    logger = setup_logger()
    cfg = setup_cfg(args)
    test_loader, num_query = build_reid_test_loader(cfg, args.dataset_name)
    demo = FeatureExtractionDemo(cfg, device=args.device, parallel=args.parallel)

    logger.info("Start extracting image features")
    feats = []
    pids = []
    camids = []
    for (feat, pid, camid) in tqdm.tqdm(demo.run_on_loader(test_loader), total=len(test_loader.loader)):
        feats.append(feat)
        pids.extend(pid)
        camids.extend(camid)

    feats = torch.cat(feats, dim=0)
    q_feat = feats[:num_query]
    g_feat = feats[num_query:]
    q_pids = np.asarray(pids[:num_query])
    g_pids = np.asarray(pids[num_query:])
    q_camids = np.asarray(camids[:num_query])
    g_camids = np.asarray(camids[num_query:])

    # compute cosine distance
    distmat = torch.mm(q_feat, g_feat.t())
    distmat = distmat.numpy()

    logger.info("Computing APs for all query images ...")
    cmc, all_ap, all_inp = evaluate_rank(1-distmat, q_pids, g_pids, q_camids, g_camids)

    visualizer = Visualizer(test_loader.loader.dataset)
    visualizer.get_model_output(all_ap, distmat, q_pids, g_pids, q_camids, g_camids)
    logger.info("Saving ranking list result ...")
    visualizer.vis_ranking_list(args.output, args.num_vis, rank_sort=args.rank_sort, max_rank=args.max_rank)
