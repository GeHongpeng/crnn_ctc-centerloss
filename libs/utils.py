import os
import numpy as np
import tensorflow as tf
import cv2
from functools import reduce
import codecs


def load_chars(filepath):
    if not os.path.exists(filepath):
        print("Chars file not exists. %s" % filepath)
        exit(1)

    ret = ''
    with open(filepath, 'r', encoding='utf-8') as f:
        while True:
            line = f.readline()
            if not line:
                break
            ret += line[0]
    return ret


def load_labels(filepath, img_num=None):
    if not os.path.exists(filepath):
        print("Label file not exists. %s" % filepath)
        exit(1)

    with open(filepath, 'r', encoding='utf-8') as f:
        labels = f.readlines()

    if img_num and img_num <= len(labels):
        labels = labels[0:img_num]

    # 移除换行符、首尾空格
    labels = [l[:-1].strip() for l in labels]
    return labels




# https://stackoverflow.com/questions/49063938/padding-labels-for-tensorflow-ctc-loss
def dense_to_sparse(dense_tensor, sparse_val=-1):
    """Inverse of tf.sparse_to_dense.

    Parameters:
        dense_tensor: The dense tensor. Duh.
        sparse_val: The value to "ignore": Occurrences of this value in the
                    dense tensor will not be represented in the sparse tensor.
                    NOTE: When/if later restoring this to a dense tensor, you
                    will probably want to choose this as the default value.
    Returns:
        SparseTensor equivalent to the dense input.
    """
    with tf.name_scope("dense_to_sparse"):
        sparse_inds = tf.where(tf.not_equal(dense_tensor, sparse_val),
                               name="sparse_inds")
        sparse_vals = tf.gather_nd(dense_tensor, sparse_inds,
                                   name="sparse_vals")
        dense_shape = tf.shape(dense_tensor, name="dense_shape",
                               out_type=tf.int64)
        return tf.SparseTensor(sparse_inds, sparse_vals, dense_shape)


def check_dir_exist(dir):
    if not os.path.exists(dir):
        os.makedirs(dir)


def restore_ckpt(sess, saver, checkpoint_dir):
    # ckpt = tf.train.latest_checkpoint(checkpoint_dir)
    ckpt = './output_20200918/checkpoint/default/ctc_center'
    try:
        saver.restore(sess, ckpt)
        print('Restore checkpoint from {}'.format(ckpt))
    except Exception as e:
        print(e)
        print("Can not restore from {}".format(checkpoint_dir))
        exit(-1)


def count_tf_params():
    """print number of trainable variables"""

    def size(v):
        return reduce(lambda x, y: x * y, v.get_shape().as_list())

    n = sum(size(v) for v in tf.trainable_variables())
    print("Tensorflow Model size: %dK" % (n / 1000,))
    return n


def get_img_paths_and_labels(img_dir):
    """label 位于文件名中"""
    img_paths = []
    labels = []

    for root, sub_folder, file_list in os.walk(img_dir):
        for idx, file_name in enumerate(sorted(file_list)):
            image_path = os.path.join(root, file_name)
            img_paths.append(image_path)

            # 00000_abcd.png
            label = file_name[:-4].split('_')[1]
            labels.append(label)

    return img_paths, labels


def get_img_paths_and_labels2(img_dir):
    """label 位于同名 txt 文件中"""
    img_paths = []
    labels = []

    def read_label(p):
        with open(p, mode='r', encoding='utf-8') as f:
            data = f.read()
        return data

    for root, sub_folder, file_list in os.walk(img_dir):
        for idx, file_name in enumerate(sorted(file_list)):
            if file_name.endswith('.jpg') and os.path.exists(os.path.join(img_dir, file_name)):
                image_path = os.path.join(root, file_name)
                img_paths.append(image_path)
                label_path = os.path.join(root, file_name[:-4] + '.txt')
                labels.append(read_label(label_path))
            else:
                print('file not found: {}'.format(file_name))

    return img_paths, labels


def get_img_paths_and_label_paths(img_dir, img_count):
    img_paths = []
    label_paths = []
    for i in range(img_count):
        base_name = "{:08d}".format(i)
        img_path = os.path.join(img_dir, base_name + ".jpg")
        label_path = os.path.join(img_dir, base_name + ".txt")
        img_paths.append(img_path)
        label_paths.append(label_path)

    return img_paths, label_paths


def build_img_paths(img_dir, img_count):
    """
    Image name should be eight length with continue num. e.g. 00000000.jpg, 00000001.jgp
    """
    img_paths = []
    for i in range(img_count):
        base_name = "{:08d}".format(i)
        img_path = os.path.join(img_dir, base_name + ".jpg")
        img_paths.append(img_path)

    return img_paths


def load_img_paths_and_labels(anno_txt):
    with codecs.open(anno_txt, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    img_paths = []
    img_labels = []
    for i, line in enumerate(lines):
        try:
            img_path, label = line.strip().split('\t')
            img_paths.append(img_path)
            img_labels.append(label)
        except:
            print(i)

    return img_paths, img_labels

def ctc_label(p, weights, w0, blank_index):
    """
    返回每个字符的索引，分数和位置
    :param p:
    :param weights:
    :param w0:
    :return:
    """
    p = list(p)
    ret = []
    ret_weight = []
    ret_position = []

    p1 = [blank_index] + p
    if len(p) > 0:
        span = w0 / float(len(p))
    else:
        span = 0
    for i in range(len(p)):
        c1 = p1[i]
        c2 = p1[i + 1]
        if c2 == blank_index or c2 == c1:
            continue
        ret.append(c2)
        ret_weight.append(weights[i])
        ret_position.append(i * span)
    char_span = 0
    for i in range(len(ret_position) - 1):
        char_span += ret_position[i + 1] - ret_position[i]
    char_span /= len(ret_position)+1

    return ret, ret_weight, ret_position


def edit_distance(src, dst, normalize=True):
    """
    http://www.dreamxu.com/books/dsa/dp/edit-distance.html
    https://en.wikipedia.org/wiki/Levenshtein_distance
    https://www.quora.com/How-do-I-figure-out-how-to-iterate-over-the-parameters-and-write-bottom-up-solutions-to-dynamic-programming-related-problems/answer/Michal-Danil%C3%A1k?srid=3OBi&share=1

    编辑距离(Levenshtein distance 莱文斯坦距离)
    给定 2 个字符串 a, b. 编辑距离是将 a 转换为 b 的最少操作次数，操作只允许如下 3 种：

    1. 插入一个字符，例如：fj -> fxj
    2. 删除一个字符，例如：fxj -> fj
    3. 替换一个字符，例如：jxj -> fyj
    """

    m = len(src)
    n = len(dst)

    # 初始化二位数组，保存中间值。多一维可以用来处理 src/dst 为空字符串的情况
    # d[i, j] 表示 src[0,i] 与 dst[0,j] 之间的距离
    d = np.zeros((n + 1, m + 1))
    #     print(d.shape)

    # 第一列赋值
    for i in range(1, n + 1):
        d[i][0] = i

    # 第一行赋值
    for j in range(1, m + 1):
        d[0][j] = j

    for j in range(1, m + 1):
        for i in range(1, n + 1):
            if src[j - 1] == dst[i - 1]:
                cost = 0
            else:
                cost = 1
            d[i, j] = min(d[i - 1, j] + 1,
                          d[i, j - 1] + 1,
                          d[i - 1, j - 1] + cost)

    distance = d[-1][-1]

    if normalize:
        if len(src) == 0 and len(dst) == 0:
            return 0

        return distance / len(src)
    else:
        return distance


def round_up(n):
    k = n * 10 % 10
    if k < 5:
        return int(n)
    else:
        return int(n) + 1

def get_char_segment(char_poses):
    """
    获取 单个字符 在原图上的位置
    :param char_poses: position of chars，2D array of shape (num of chars, 2) 最后一个维度是 (字符输出的时间步，图片在 batch 中的序号)
    :return: segments
    :rtype: list of list of slice object

    >>> char_pos = np.array([[5,0],[9,0],[12,0],[16,0]])
    >>> char_seg = get_char_segment(char_pos)
    [[slice(0, 32, None), slice(32, 48, None), slice(48, 60, None), slice(60, None, None)]]
    """

    # 将同一张图片的 char_pos 整合在一起，便于后续计算
    char_poses = char_poses.tolist()
    cur_img_index = char_poses[0][1]
    pos = []
    poses = []
    for p in char_poses:
        if p[1] != cur_img_index:
            poses.append(pos)
            pos = []
            cur_img_index = p[1]
        pos.append(p[0])
    poses.append(pos)

    # 计算 char_segment
    char_segments = []
    start = 0
    for char_pos in poses:
        char_segment = []
        for i, pos in enumerate(char_pos):
            # 注：此处是粗略计算，更适合汉字场景，如果数字、字母等场景需要较高精确度，则可以细化此处计算
            if i != 0:
                start = np.math.ceil((start + char_pos[i]) / 2) * 4
            try:
                end = np.math.ceil((char_pos[i] + char_pos[i + 1]) / 2) * 4
            except IndexError:
                end = None

            char_segment.append(slice(start, end))
            start = pos
        char_segments.append(char_segment)
        start = 0

    return char_segments

def resize_batch_image_single(imgs, out_height, out_width):
    """
    resize 图片，使图片的大小均为 (32,32)，以输出 embedding 的 sprite 图
    :param imgs: 图片列表
    :param out_height: 输出高度，一般为 32
    :param out_width: 输出宽度，一般为 32
    :return:
    """
    target_image_list = []
    for img in imgs:
        h, w = img.shape[:2]
        if w < 32:
            out_img = np.pad(img, pad_width=((0, 0),
                                             (0, out_width - w),
                                             (0, 0)),
                                  mode="constant",
                                  constant_values=(255,))
        # 否则，resize
        else:
            out_img = cv2.resize(img, (out_height, out_width), interpolation=cv2.INTER_AREA)
        target_image_list.append(out_img)

    return target_image_list


if __name__ == '__main__':
    char_pos = np.array([[5,0],[9,0],[12,0],[16,0]])
    char_seg = get_char_segment(char_pos)
    print()