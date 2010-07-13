import sys
import struct
from collections import namedtuple
from yapgvb import Digraph
from optparse import OptionParser

LEAF_TYPE = 1
INTERNAL_TYPE = 2
BLOCK_SIZE = 2048
Pair = namedtuple('Pair', 'key, value')

def parse_pair(block, offset, is_leaf):
    assert offset < BLOCK_SIZE
    key = get_key(block, offset + (0 if is_leaf else 8))
    if is_leaf:
        value = get_value(block, offset)
    else:
        value = get_lnode(block, offset)
    return Pair(key, value)

def get_key(block, offset):
    key_len, = struct.unpack_from('B', block, offset)
    key, = struct.unpack_from('%is' % key_len, block, offset + 1)
    return key

def get_value(block, offset):
    key_len, = struct.unpack_from('B', block, offset)
    offset += 1 + key_len
    value_len, = struct.unpack_from('H', block, offset)
    value, = struct.unpack_from('%is' % value_len, block, offset + 4)
    return value

def get_lnode(block, offset):
    lnode, = struct.unpack_from('Q', block, offset)
    return lnode

    
def process(g, data, node_offset, verbose):
    data.seek(node_offset)
    node = data.read(BLOCK_SIZE)
    
    #assume root is leaf for now
    node_type, npairs, frontmost_offset = struct.unpack_from('IHH', node)
    assert node_type == LEAF_TYPE or node_type == INTERNAL_TYPE
    is_leaf = node_type == LEAF_TYPE
    
    offsets = struct.unpack_from('%iH' % npairs, node, 8)

    pairs = map(lambda offset: parse_pair(node, offset, is_leaf), offsets)
    if verbose:
        print "Node %i:" % node_offset
        print pairs
        print "------------------"


    node_cluster = g.subgraph("cluster %i" % node_offset)

    num = len(pairs)
    if is_leaf:
        for i, pair in enumerate(pairs):
            graph_node = node_cluster.add_node(label = "%s | %s" % pair)
            if (i == num//2):
                anchor = graph_node
    else:
        for i, pair in enumerate(pairs):
            graph_node = node_cluster.add_node(label = pair.key)
            target = process(g, data, pair.value, verbose)
            edge = g.add_edge(graph_node, target)
            edge.lhead = "cluster %i" % pair.value
            if (i == num//2):
                anchor = graph_node

    return anchor
        

def main(argv):
    parser = OptionParser("usage: %prog [options] INPUT_FILE")
    parser.add_option("-o", dest="output_file", help="output to specified file (guesses format from extension). [default: %default]", default="tree.svg")
    parser.add_option("-v", "--verbose", dest="verbose", help="prints the contents of the nodes as it scans them", action="store_true")
    options, args = parser.parse_args()

    if len(args) != 1:
        parser.error("incorrect number of arguments")

    data = open(args[0], 'rb')
    
    superblock = data.read(BLOCK_SIZE)
    root_offset = struct.unpack_from('I', superblock)[0] #always unpacks into a tuple

    g = Digraph("RethinkDB Visualization")
    g.compound = True
    g.ranksep = "4 equally"
    process(g, data, root_offset, options.verbose)

    g.layout("dot")
    g.render(options.output_file)
        
if __name__ == '__main__':
    sys.exit(main(sys.argv))
