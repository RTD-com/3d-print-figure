"""八视角命名和图片质量阈值的唯一代码来源。"""

VIEWS = (
    ('01_top.png', 'top'), ('02_left45.png', 'left45'),
    ('03_front.png', 'front'), ('04_right45.png', 'right45'),
    ('05_left.png', 'left'), ('06_right.png', 'right'),
    ('07_back.png', 'back'), ('08_bottom.png', 'bottom'),
)
EXPECTED = tuple(name for name, _ in VIEWS)
MIN_BACKGROUND_RATIO = 0.10
WHITE_CHANNEL_MIN = 250
ASPECT_RATIO = 1.0


def selected_files(expected=8, views=None):
    """显式 subset 必须和 expected 一致，禁止静默取前 N 张。"""
    if views:
        tokens = views.split(',') if isinstance(views, str) else list(views)
        aliases = {slot: name for name, slot in VIEWS}
        aliases.update({name: name for name in EXPECTED})
        try:
            files = [aliases[token.strip()] for token in tokens]
        except KeyError as exc:
            raise ValueError('未知视角: {}'.format(exc.args[0])) from exc
    else:
        files = list(EXPECTED)
    if len(files) != expected or len(set(files)) != len(files):
        raise ValueError('--expected 必须与不重复的 --views 集合数量一致；默认要求完整 8 张')
    return files
