"""Настройки BiRefNet, под которые обучены веса BiRefNet-general-bb_swin_v1_tiny-epoch_232.

Правка проекта: в оригинале (config.py) — пути датасетов, обучение и выбор из всех
backbone. Здесь только то, что читает модель при выводе маски, — значения сняты с
оригинала (task='General', bb='swin_v1_t') на коммите из README.md этой папки.
"""


class Config:
    task = 'General'
    bb = 'swin_v1_t'
    ms_supervision = True
    out_ref = True
    dec_ipt = True
    dec_ipt_split = True
    cxt_num = 3
    mul_scl_ipt = 'cat'
    dec_att = 'ASPPDeformable'
    squeeze_block = 'BasicDecBlk_x1'
    dec_blk = 'BasicDecBlk'
    lat_blk = 'BasicLatBlk'
    dec_channels_inter = 'fixed'
    auxiliary_classification = False
    freeze_bb = False
    batch_size = 8              # при обучении; от него зависит, есть ли BatchNorm в блоках — веса с ним
    SDPA_enabled = True
    # swin_v1_t: [768, 384, 192, 96], удвоены из-за mul_scl_ipt='cat'
    lateral_channels_in_collection = [1536, 768, 384, 192]
    cxt = [192, 384, 768]       # lateral_channels_in_collection[1:][::-1][-cxt_num:]
