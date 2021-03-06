#!/usr/bin/env python3

import argparse, sys, os, stat, pwd, grp, time, hashlib

pargs = argparse.ArgumentParser(
    description='List files and folders renovated. Useful to verify is things have changed.',
    epilog='Typical non-recursive usage: lsha.py -citxp .  (otherwise just -a)'
)

pargs.add_argument('-c', default=False, dest='checksum', action='store_const', const=True, help='checksum files')
pargs.add_argument('-r', default=False, dest='recursive', action='store_const', const=True, help='walk recursively')
pargs.add_argument('-i', default=False, dest='hidden', action='store_const', const=True, help='include hidden files')
pargs.add_argument('-t', default=False, dest='timestamp', action='store_const', const=True, help='include timestamps')
pargs.add_argument('-x', default=False, dest='xattrs', action='store_const', const=True, help='include xattrs')
pargs.add_argument('-p', default=False, dest='perms', action='store_const', const=True, help='include permissions')
pargs.add_argument('-f', default=False, dest='file_path', action='store_const', const=True, help='path + file per-line')
pargs.add_argument('-a', default=False, dest='all', action='store_const', const=True, help='include everything')
pargs.add_argument('-c:md5', dest='algo', action='store_const', const='md5', help='use md5 checksum')
pargs.add_argument('-c:sha1', dest='algo', action='store_const', const='sha1', help='use sha1 checksum')
pargs.add_argument('-c:sha256', dest='algo', action='store_const', const='sha256', help='use sha256 checksum (default)')
pargs.add_argument('-c:sha384', dest='algo', action='store_const', const='sha384', help='use sha384 checksum')
pargs.add_argument('-c:sha512', dest='algo', action='store_const', const='sha512', help='use sha512 checksum')
pargs.add_argument('-e:x', dest='xattrs', action='store_const', const='EXCL', help='disable xattrs (useful after -a)')
pargs.add_argument('-e:c', dest='checksum', action='store_const', const='EXCL', help='disable checksum (")')
pargs.add_argument('path', type=str, nargs='+', help='path to lsha.py!')
arguments = pargs.parse_args()


def arg_applies(arg):
    return (arg or arguments.all) and arg is not 'EXCL'


def is_hidden(path):
    name = os.path.basename(os.path.abspath(path))
    return name.startswith('.')


def do_checksum(args, fullpath):
    if args.algo == 'md5':
        h = hashlib.md5()
    elif args.algo == 'sha1':
        h = hashlib.sha1()
    elif args.algo == 'sha384':
        h = hashlib.sha384()
    elif args.algo == 'sha512':
        h = hashlib.sha512()
    else: # default
        h = hashlib.sha256()
    with open(fullpath, 'rb') as f:
        for chunk in iter(lambda: f.read(65535), b""):
            h.update(chunk)
    return h.hexdigest()


def get_mock_checksum(args):
    base = ':.'
    if args.algo == 'md5': return base * 16
    elif args.algo == 'sha1': return base * 20
    elif args.algo == 'sha384': return base * 48
    elif args.algo == 'sha512': return base * 64
    return base * 32


def rwx(mode, rm, wm, xm):
    r = 'r' if mode & rm == rm else '-'
    r += 'w' if mode & wm == wm else '-'
    r += 'x' if mode & xm == xm else '-'
    return r


def dbpcs(mode):
    if mode & stat.S_IFLNK == stat.S_IFLNK: return 's'
    if mode & stat.S_IFSOCK == stat.S_IFSOCK: return 's'
    if mode & stat.S_IFREG == stat.S_IFREG: return '-'
    if mode & stat.S_IFBLK == stat.S_IFBLK: return 'b'
    if mode & stat.S_IFDIR == stat.S_IFDIR: return 'd'
    if mode & stat.S_IFIFO == stat.S_IFIFO: return 'p'
    if mode & stat.S_IFCHR == stat.S_IFCHR: return 'c'
    return '?'


def stats_to_str(s):
    return "%s%s%s%s" % (dbpcs(s.st_mode),
        rwx(s.st_mode, stat.S_IRUSR, stat.S_IWUSR, stat.S_IXUSR),
        rwx(s.st_mode, stat.S_IRGRP, stat.S_IWGRP, stat.S_IXGRP),
        rwx(s.st_mode, stat.S_IROTH, stat.S_IWOTH, stat.S_IXOTH))


def xt_to_str(xt):
    if len(xt.keys()) == 0:
        return ''
    r = '\n'
    for key in xt.keys():
        h = hashlib.md5()
        h.update(xt[key])
        val = xt[key]
        if len(val) > 10:
            value = str(val[:10]) + ' (%i bytes)' % len(val)
        else:
            value = str(val)
        r += ' +xattr (md5:%s) %s = %s \n' % (h.hexdigest(), key, value)
    return r[:-1]


def do_entry(args, path, filename):
    fullpath = "%s/%s" % (path, filename)
    if is_hidden(fullpath) and not (args.hidden or args.all):
        return

    stats = os.stat(fullpath)
    passwd = pwd.getpwuid(stats.st_uid)
    group = grp.getgrgid(stats.st_gid)
    if arg_applies(args.xattrs):
        xt = xattr.xattr(fullpath)
    else:
        xt = {}

    out = ''
    if arg_applies(args.checksum):
        if dbpcs(stats.st_mode)[0] == '-':
            out += do_checksum(args, fullpath) + '  '
        else:
            out += get_mock_checksum(args) + '  '
    if args.perms or args.all:
        out += stats_to_str(stats)
        out += "%6s %6s " % (passwd.pw_name, group.gr_name)
    out += "%11i " % stats.st_size
    if args.timestamp or args.all:
        out += time.strftime("%Y-%m-%d %H:%M:%S %Z ", time.gmtime(stats.st_mtime))
    if args.file_path or args.all:
        out += path + '/'
    out += filename
    if arg_applies(args.xattrs):
        out += xt_to_str(xt)

    print(out)
    sys.stdout.flush()


def do_path(args, path):
    if is_hidden(path) and not (args.hidden or args.all):
        return

    for dirpath, dirnames, filenames in os.walk(path):
        dirnames.sort()
        filenames.sort()
        print(dirpath)
        for dir_name in dirnames:
            do_entry(args, dirpath, dir_name)
        for filename in filenames:
            do_entry(args, dirpath, filename)
        print()

        if not (args.recursive or args.all):
            break



# main

if arg_applies(arguments.xattrs):
    try:
        import xattr
    except ImportError:
        print('please install xattr to use -x option (can be implied by -a)')
        sys.exit(-1)


for path in arguments.path:
    if os.path.isfile(path):
        do_entry(arguments, path)
    else:
        while path[-1] == '/':
            path = path[0:-1]
        do_path(arguments, path)

print('lsha.py:EOF')
