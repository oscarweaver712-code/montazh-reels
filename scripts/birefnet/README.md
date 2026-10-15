# BiRefNet — код модели

Источник: https://github.com/ZhengPeng7/BiRefNet, коммит `c4d649666cc171486329413dc2b61f0137158b6a`
(11.10.2026). Лицензия — MIT (`LICENSE` рядом). Веса — `models.py`, ключ `birefnet_lite`.

Взято для вывода маски (`matte.py --backend birefnet`), обучение не поддерживается. Правки проекта:

- `birefnet.py` — убраны einops, kornia, huggingface_hub и dataset; `image2patches` на reshape/permute;
  backbone строится только swin_v1_t, без загрузки частичных весов.
- `swin_v1.py` — `DropPath`, `to_2tuple`, `trunc_normal_` из `_layers.py` вместо timm.
- `aspp.py`, `decoder_blocks.py`, `lateral_blocks.py` — относительные импорты.
- `config.py` — только поля, которые модель читает при выводе, со значениями оригинала (task General).

Файлы `deform_conv.py`, `aspp.py`, `decoder_blocks.py`, `lateral_blocks.py`, `swin_v1.py` — оригиналы
с правкой импортов. Сверка с оригиналом (14.10.2026, кадр IMG_1803 на 44 с, 768×768, процессор, fp32):
все ключи весов совпали, маска совпала точно — расхождение 0,0.
