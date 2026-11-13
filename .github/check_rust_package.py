"""Check the actual client crate carries its source and canonical MIT license."""
import pathlib
import re
import sys
import tarfile


def check(directory, license_file):
    packages = list(pathlib.Path(directory).glob('decklogic-simlib-client-*.crate'))
    if len(packages) != 1:
        raise ValueError('expected exactly one Rust client crate')
    package = packages[0]
    prefix = package.stem + '/'
    with tarfile.open(package, 'r:gz') as archive:
        members = archive.getmembers()
        names = [member.name for member in members]
        if len(names) != len(set(names)):
            raise ValueError('duplicate crate members')
        for relative in ['Cargo.toml', 'src/lib.rs', 'LICENSE']:
            member = archive.getmember(prefix + relative)
            if not member.isfile():
                raise ValueError('required crate entry is not a regular file')
        metadata = archive.extractfile(prefix + 'Cargo.toml').read().decode('utf-8')
        if not re.search(r'^license\s*=\s*"MIT"\s*$', metadata, re.MULTILINE):
            raise ValueError('crate metadata must declare MIT')
        if archive.extractfile(prefix + 'LICENSE').read() != pathlib.Path(license_file).read_bytes():
            raise ValueError('crate license differs from repository license')
    return package.name


if __name__ == '__main__':
    print('checked ' + check(*sys.argv[1:]))
