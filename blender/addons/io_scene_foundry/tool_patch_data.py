"""Verified MCC Tool import patches, expressed as PE file offsets.

Each profile is keyed by (machine, COFF timestamp, SizeOfImage), independently
of the installation directory or executable name. Every record also validates
the surrounding instructions. See TOOL_PATCHES.md for scope and verification.
No disassembler or third-party package is required at runtime.
"""


def _record(offset, original, replacement):
    return offset, bytes.fromhex(replacement), bytes.fromhex(original)


IMPORT_PATCH_PROFILES = {
    # halo2: tool.exe
    (0x14C, 0x6491EFB1, 0x1B4F000): (
        'halo2', 'tool', {
            'skip_vertex_compression': (
                _record(0x9C315, "0f 8e 64 03 00 00",
                        "90 e9 64 03 00 00"),
                _record(0x7B63C, "0f 8e b9 03 00 00",
                        "90 e9 b9 03 00 00"),
            ),
            'uncompressed_vertex_weights': (
                _record(0xB760A, "83 7e 4c 00 0f 8e 04 04 00 00",
                        "83 7e 4c 00 90 e9 04 04 00 00"),
            ),
            'plane_builder': (
                _record(0x8E445, "75 35 6a 01 68 92 03 00 00",
                        "eb 35 6a 01 68 92 03 00 00"),
                _record(0x8E496, "75 35 6a 01 68 93 03 00 00",
                        "eb 35 6a 01 68 93 03 00 00"),
                _record(0x8E4E7, "75 35 6a 01 68 94 03 00 00",
                        "eb 35 6a 01 68 94 03 00 00"),
            ),
            'skip_import_source_data': (
                _record(0x27D402, "ff b5 dc fe ff ff 89 85 e0 fe ff ff 05 88 01 00 00 50 e8 87 f4 fb ff 83 c4 14",
                        "89 85 e0 fe ff ff 8b b5 f8 fe ff ff 83 c4 0c e9 6f 00 00 00 90 90 90 90 90 90"),
            ),
        },
    ),
    # halo2: tool_fast.exe
    (0x14C, 0x6491F037, 0x13A9000): (
        'halo2', 'tool_fast', {
            'skip_vertex_compression': (
                _record(0x6884E, "0f 8e bf 02 00 00",
                        "90 e9 bf 02 00 00"),
                _record(0x4E9F9, "0f 8e a7 03 00 00",
                        "90 e9 a7 03 00 00"),
            ),
            'uncompressed_vertex_weights': (
                _record(0x729EA, "39 48 4c 0f 8e ba 01 00 00",
                        "39 48 4c 90 e9 ba 01 00 00"),
            ),
            'skip_import_source_data': (
                _record(0x181C3D, "8b 7c 24 14 8d 8e 88 01 00 00",
                        "8b 7c 24 28 e9 54 00 00 00 90"),
            ),
        },
    ),
    # halo3: tool.exe
    (0x8664, 0x6595A3A1, 0x19B31000): (
        'halo3', 'tool', {
            'skip_vertex_compression': (
                _record(0x134CCC, "0f 8e 73 04 00 00 48 89 ac 24 c8 00 00 00",
                        "48 e9 73 04 00 00 48 89 ac 24 c8 00 00 00"),
                _record(0x1049F5, "0f 8e ff 05 00 00 48 89 58 e8 4c 89 60 d8",
                        "48 e9 ff 05 00 00 48 89 58 e8 4c 89 60 d8"),
            ),
            'uncompressed_vertex_weights': (
                _record(0x15E056, "83 79 6c 00 0f 8e 46 03 00 00 ba 0c 00 00 00 48 8d 48",
                        "83 79 6c 00 48 e9 46 03 00 00 ba 0c 00 00 00 48 8d 48"),
            ),
            'plane_builder': (
                _record(0x120FCD, "77 1b 48 8d 0d ca e4 e9 00 e8 25 0d 68 00",
                        "eb 1b 48 8d 0d ca e4 e9 00 e8 25 0d 68 00"),
                _record(0x121030, "77 1b 48 8d 0d ef e4 e9 00 e8 c2 0c 68 00",
                        "eb 1b 48 8d 0d ef e4 e9 00 e8 c2 0c 68 00"),
                _record(0x12108C, "77 0c 48 8d 0d 13 e5 e9 00 e8 66 0c 68 00",
                        "eb 0c 48 8d 0d 13 e5 e9 00 e8 66 0c 68 00"),
                _record(0x108A6B, "77 0c 48 8d 0d 64 87 ea 00 e8 87 92 69 00",
                        "eb 0c 48 8d 0d 64 87 ea 00 e8 87 92 69 00"),
                _record(0xFC761, "77 0c 48 8d 0d fe c0 eb 00 e8 91 55 6a 00",
                        "eb 0c 48 8d 0d fe c0 eb 00 e8 91 55 6a 00"),
            ),
            'skip_import_source_data': (
                _record(0x81C255, "48 8d 88 30 01 00 00 e8 ff ca f9 ff",
                        "e9 66 00 00 00 90 90 90 90 90 90 90"),
            ),
        },
    ),
    # halo3: tool_fast.exe
    (0x8664, 0x6595A253, 0x199BE000): (
        'halo3', 'tool_fast', {
            'skip_vertex_compression': (
                _record(0xEB8E0, "0f 8e 04 06 00 00 48 89 ac 24 e0 00 00 00",
                        "48 e9 04 06 00 00 48 89 ac 24 e0 00 00 00"),
                _record(0xB12C4, "0f 8e aa 05 00 00 48 89 58 e8 48 89 78 d8",
                        "48 e9 aa 05 00 00 48 89 58 e8 48 89 78 d8"),
            ),
            'uncompressed_vertex_weights': (
                _record(0x103FA8, "83 79 6c 00 0f 8e f3 02 00 00 8d 55 08 48 8d 48 80 e8",
                        "83 79 6c 00 48 e9 f3 02 00 00 8d 55 08 48 8d 48 80 e8"),
            ),
            'plane_builder': (
                _record(0xD62B8, "77 21 48 8d 0d 77 70 2f 01 e8 7a 6f 6b 00",
                        "eb 21 48 8d 0d 77 70 2f 01 e8 7a 6f 6b 00"),
                _record(0xD6327, "77 21 48 8d 0d b0 70 2f 01 e8 0b 6f 6b 00",
                        "eb 21 48 8d 0d b0 70 2f 01 e8 0b 6f 6b 00"),
                _record(0xD638D, "77 0c 48 8d 0d ba 69 2f 01 e8 a5 6e 6b 00",
                        "eb 0c 48 8d 0d ba 69 2f 01 e8 a5 6e 6b 00"),
                _record(0xB43CD, "77 0c 48 8d 0d 0a bf 30 01 e8 65 8e 6d 00",
                        "eb 0c 48 8d 0d 0a bf 30 01 e8 65 8e 6d 00"),
                _record(0xBD111, "77 0c 48 8d 0d 9e 2c 30 01 e8 21 01 6d 00",
                        "eb 0c 48 8d 0d 9e 2c 30 01 e8 21 01 6d 00"),
            ),
            'skip_import_source_data': (
                _record(0x7E3F41, "48 8d 8f 30 01 00 00 e8 a3 68 fb ff",
                        "e9 66 00 00 00 90 90 90 90 90 90 90"),
            ),
        },
    ),
    # halo3odst: tool.exe
    (0x8664, 0x64F22702, 0x1940D000): (
        'halo3odst', 'tool', {
            'skip_vertex_compression': (
                _record(0x13980C, "0f 8e 73 04 00 00 48 89 ac 24 c8 00 00 00",
                        "48 e9 73 04 00 00 48 89 ac 24 c8 00 00 00"),
                _record(0x108E35, "0f 8e 05 06 00 00 48 89 58 e8 4c 89 60 d8",
                        "48 e9 05 06 00 00 48 89 58 e8 4c 89 60 d8"),
            ),
            'uncompressed_vertex_weights': (
                _record(0x1616A6, "83 79 6c 00 0f 8e 46 03 00 00 ba 0c 00 00 00 48 8d 48",
                        "83 79 6c 00 48 e9 46 03 00 00 ba 0c 00 00 00 48 8d 48"),
            ),
            'plane_builder': (
                _record(0x1253AD, "77 1b 48 8d 0d aa 52 f2 00 e8 85 d8 6b 00",
                        "eb 1b 48 8d 0d aa 52 f2 00 e8 85 d8 6b 00"),
                _record(0x125410, "77 1b 48 8d 0d cf 52 f2 00 e8 22 d8 6b 00",
                        "eb 1b 48 8d 0d cf 52 f2 00 e8 22 d8 6b 00"),
                _record(0x12546C, "77 0c 48 8d 0d f3 52 f2 00 e8 c6 d7 6b 00",
                        "eb 0c 48 8d 0d f3 52 f2 00 e8 c6 d7 6b 00"),
                _record(0x10CEBB, "77 0c 48 8d 0d 14 f5 f2 00 e8 77 5d 6d 00",
                        "eb 0c 48 8d 0d 14 f5 f2 00 e8 77 5d 6d 00"),
                _record(0x100B81, "77 0c 48 8d 0d de 2e f4 00 e8 b1 20 6e 00",
                        "eb 0c 48 8d 0d de 2e f4 00 e8 b1 20 6e 00"),
            ),
            'skip_import_source_data': (
                _record(0x866215, "48 8d 88 30 01 00 00 e8 9f 39 f9 ff",
                        "e9 66 00 00 00 90 90 90 90 90 90 90"),
            ),
        },
    ),
    # halo3odst: tool_fast.exe
    (0x8664, 0x64F227DE, 0x19290000): (
        'halo3odst', 'tool_fast', {
            'skip_vertex_compression': (
                _record(0xEFF30, "0f 8e 04 06 00 00 48 89 ac 24 e0 00 00 00",
                        "48 e9 04 06 00 00 48 89 ac 24 e0 00 00 00"),
                _record(0xB4684, "0f 8e bc 05 00 00 48 89 58 e8 48 89 78 d8",
                        "48 e9 bc 05 00 00 48 89 58 e8 48 89 78 d8"),
            ),
            'uncompressed_vertex_weights': (
                _record(0x107888, "83 79 6c 00 0f 8e f3 02 00 00 8d 55 08 48 8d 48 80 e8",
                        "83 79 6c 00 48 e9 f3 02 00 00 8d 55 08 48 8d 48 80 e8"),
            ),
            'plane_builder': (
                _record(0xD95F8, "77 21 48 8d 0d ef 1e 39 01 e8 8a 3c 6f 00",
                        "eb 21 48 8d 0d ef 1e 39 01 e8 8a 3c 6f 00"),
                _record(0xD9667, "77 21 48 8d 0d 28 1f 39 01 e8 1b 3c 6f 00",
                        "eb 21 48 8d 0d 28 1f 39 01 e8 1b 3c 6f 00"),
                _record(0xD96CD, "77 0c 48 8d 0d 32 18 39 01 e8 b5 3b 6f 00",
                        "eb 0c 48 8d 0d 32 18 39 01 e8 b5 3b 6f 00"),
                _record(0xB77BC, "77 0c 48 8d 0d cb a5 3a 01 e8 c6 5a 71 00",
                        "eb 0c 48 8d 0d cb a5 3a 01 e8 c6 5a 71 00"),
                _record(0xC0491, "77 0c 48 8d 0d fe 13 3a 01 e8 f1 cd 70 00",
                        "eb 0c 48 8d 0d fe 13 3a 01 e8 f1 cd 70 00"),
            ),
            'skip_import_source_data': (
                _record(0x828251, "48 8d 8f 30 01 00 00 e8 23 26 fb ff",
                        "e9 66 00 00 00 90 90 90 90 90 90 90"),
            ),
        },
    ),
    # reach: tool.exe
    (0x8664, 0x64B47BC1, 0x1B9F0000): (
        'reach', 'tool', {
            'skip_vertex_compression': (
                _record(0x2395EC, "0f 8e 73 04 00 00 48 89 9c 24 c8 00 00 00",
                        "48 e9 73 04 00 00 48 89 9c 24 c8 00 00 00"),
                _record(0x1E69FD, "0f 8e d1 06 00 00 49 89 5b e8 48 81 c1 58",
                        "48 e9 d1 06 00 00 49 89 5b e8 48 81 c1 58"),
            ),
            'uncompressed_vertex_weights': (
                _record(0x2B8E69, "83 79 68 00 0f 8e 80 03 00 00 ba 0c 00 00 00 48 8d 4d",
                        "83 79 68 00 48 e9 80 03 00 00 ba 0c 00 00 00 48 8d 4d"),
            ),
            'plane_builder': (
                _record(0x220CE5, "77 1b 48 8d 0d da c7 9f 01 e8 cd 83 5d 00",
                        "eb 1b 48 8d 0d da c7 9f 01 e8 cd 83 5d 00"),
                _record(0x220D55, "77 1b 48 8d 0d ea c7 9f 01 e8 5d 83 5d 00",
                        "eb 1b 48 8d 0d ea c7 9f 01 e8 5d 83 5d 00"),
                _record(0x220DBB, "77 0c 48 8d 0d 04 c8 9f 01 e8 f7 82 5d 00",
                        "eb 0c 48 8d 0d 04 c8 9f 01 e8 f7 82 5d 00"),
                _record(0x1ED91A, "77 0c 48 8d 0d 95 04 a1 01 e8 98 b7 60 00",
                        "eb 0c 48 8d 0d 95 04 a1 01 e8 98 b7 60 00"),
                _record(0x1DA98B, "77 0c 48 8d 0d 84 aa a2 01 e8 27 e7 61 00",
                        "eb 0c 48 8d 0d 84 aa a2 01 e8 27 e7 61 00"),
            ),
            'node_depth_sort': (
                _record(0x25ED90, "8b 14 80 41 ff c2 45 2b ca 75 5b 44 8b 49 14 44",
                        "8b 14 80 41 ff c2 45 2b ca 90 90 44 8b 49 14 44"),
                _record(0x25ECEB, "8b 41 18 2b 42 18 75 49 8b 81 f8 01 00 00 2b 82",
                        "8b 41 18 2b 42 18 90 90 8b 81 f8 01 00 00 2b 82"),
            ),
            'skip_import_source_data': (
                _record(0x270E0F, "41 89 81 44 01 00 00 e8 25 10 90 00",
                        "41 89 81 44 01 00 00 90 90 90 90 90"),
            ),
        },
    ),
    # reach: tool_fast.exe
    (0x8664, 0x64B47C63, 0x1ABC7000): (
        'reach', 'tool_fast', {
            'skip_vertex_compression': (
                _record(0x1B50D0, "0f 8e 74 05 00 00 48 89 9c 24 e0 00 00 00",
                        "48 e9 74 05 00 00 48 89 9c 24 e0 00 00 00"),
                _record(0x15D9AD, "0f 8e ce 06 00 00 49 89 5b e8 48 81 c1 58",
                        "48 e9 ce 06 00 00 49 89 5b e8 48 81 c1 58"),
            ),
            'uncompressed_vertex_weights': (
                _record(0x21FB7B, "83 79 68 00 0f 8e 5e 03 00 00 48 c7 45 df 0c 00 00 00",
                        "83 79 68 00 48 e9 5e 03 00 00 48 c7 45 df 0c 00 00 00"),
            ),
            'plane_builder': (
                _record(0x19A9B3, "77 1e 48 8d 0d fc 82 36 01 e8 93 d4 1e 00",
                        "eb 1e 48 8d 0d fc 82 36 01 e8 93 d4 1e 00"),
                _record(0x19AA27, "77 1e 48 8d 0d 70 82 36 01 e8 1f d4 1e 00",
                        "eb 1e 48 8d 0d 70 82 36 01 e8 1f d4 1e 00"),
                _record(0x19AA91, "77 0c 48 8d 0d 4e 82 36 01 e8 b5 d3 1e 00",
                        "eb 0c 48 8d 0d 4e 82 36 01 e8 b5 d3 1e 00"),
                _record(0x1604FB, "77 0c 48 8d 0d c4 cd 38 01 e8 4b 79 22 00",
                        "eb 0c 48 8d 0d c4 cd 38 01 e8 4b 79 22 00"),
                _record(0x16966B, "77 0c 48 8d 0d 14 19 38 01 e8 db e7 21 00",
                        "eb 0c 48 8d 0d 14 19 38 01 e8 db e7 21 00"),
                _record(0x19A775, "75 0c 48 8d 0d 82 85 36 01 e8 d1 d6 1e 00",
                        "eb 0c 48 8d 0d 82 85 36 01 e8 d1 d6 1e 00"),
                _record(0x19A789, "75 0c 48 8d 0d b6 85 36 01 e8 bd d6 1e 00",
                        "eb 0c 48 8d 0d b6 85 36 01 e8 bd d6 1e 00"),
                _record(0x19A79A, "75 0c 48 8d 0d 8d 85 36 01 e8 ac d6 1e 00",
                        "eb 0c 48 8d 0d 8d 85 36 01 e8 ac d6 1e 00"),
                _record(0x1A0C86, "73 16 48 8d 0d 11 1a 36 01 e8 c0 71 1e 00",
                        "eb 16 48 8d 0d 11 1a 36 01 e8 c0 71 1e 00"),
            ),
            'node_depth_sort': (
                _record(0x1CC3B0, "8b 14 80 41 ff c2 45 2b ca 75 5b 44 8b 49 14 44",
                        "8b 14 80 41 ff c2 45 2b ca 90 90 44 8b 49 14 44"),
                _record(0x1D60CB, "8b 41 18 2b 42 18 75 49 8b 81 f8 01 00 00 2b 82",
                        "8b 41 18 2b 42 18 90 90 8b 81 f8 01 00 00 2b 82"),
            ),
            'skip_import_source_data': (
                _record(0x1DC954, "41 89 80 44 01 00 00 45 39 65 00 7e 12",
                        "41 89 80 44 01 00 00 e9 a5 03 00 00 90"),
            ),
        },
    ),
    # halo4: tool.exe
    (0x8664, 0x649B075D, 0x6E66000): (
        'halo4', 'tool', {
            'skip_vertex_compression': (
                _record(0x279BB8, "0f 8e e0 04 00 00 48 89 b4 24 d8 00 00 00",
                        "48 e9 e0 04 00 00 48 89 b4 24 d8 00 00 00"),
                _record(0x231D00, "0f 8e 35 0a 00 00 48 8d 47 48 48 89 45 b8",
                        "48 e9 35 0a 00 00 48 8d 47 48 48 89 45 b8"),
            ),
            'plane_builder': (
                _record(0x260DA5, "77 0c 48 8d 0d 6a 58 a5 01 e8 4d d5 3a 00",
                        "eb 0c 48 8d 0d 6a 58 a5 01 e8 4d d5 3a 00"),
                _record(0x260E17, "77 0c 48 8d 0d 78 58 a5 01 e8 db d4 3a 00",
                        "eb 0c 48 8d 0d 78 58 a5 01 e8 db d4 3a 00"),
                _record(0x260E85, "77 0c 48 8d 0d 8a 58 a5 01 e8 6d d4 3a 00",
                        "eb 0c 48 8d 0d 8a 58 a5 01 e8 6d d4 3a 00"),
                _record(0x236DFD, "77 0c 48 8d 0d a2 52 a6 01 e8 f5 74 3d 00",
                        "eb 0c 48 8d 0d a2 52 a6 01 e8 f5 74 3d 00"),
                _record(0x2269B4, "77 0c 48 8d 0d 2b cd a7 01 e8 3e 79 3e 00",
                        "eb 0c 48 8d 0d 2b cd a7 01 e8 3e 79 3e 00"),
            ),
            'skip_import_source_data': (
                _record(0x1FD799, "41 89 81 44 01 00 00 8b d7 49 8b cc e8 b6 67 6c 00",
                        "41 89 81 44 01 00 00 8b d7 49 8b cc 90 90 90 90 90"),
            ),
        },
    ),
    # halo4: tool_fast.exe
    (0x8664, 0x649B0A11, 0x6644000): (
        'halo4', 'tool_fast', {
            'skip_vertex_compression': (
                _record(0x2B044C, "0f 8e f4 05 00 00 48 89 ac 24 d8 00 00 00",
                        "48 e9 f4 05 00 00 48 89 ac 24 d8 00 00 00"),
                _record(0x24D402, "0f 8e ce 14 00 00 49 8d 46 48 48 89 45 f0",
                        "48 e9 ce 14 00 00 49 8d 46 48 48 89 45 f0"),
            ),
            'plane_builder': (
                _record(0x28FD1E, "77 0c 48 8d 0d e9 f1 68 01 e8 88 c2 28 00",
                        "eb 0c 48 8d 0d e9 f1 68 01 e8 88 c2 28 00"),
                _record(0x28FD90, "77 0c 48 8d 0d ff f0 68 01 e8 16 c2 28 00",
                        "eb 0c 48 8d 0d ff f0 68 01 e8 16 c2 28 00"),
                _record(0x28FDFE, "77 0c 48 8d 0d a9 f0 68 01 e8 a8 c1 28 00",
                        "eb 0c 48 8d 0d a9 f0 68 01 e8 a8 c1 28 00"),
                _record(0x251343, "75 0c 48 8d 0d 5c 97 6b 01 e8 63 ac 2c 00",
                        "eb 0c 48 8d 0d 5c 97 6b 01 e8 63 ac 2c 00"),
                _record(0x25B5D4, "77 0c 48 8d 0d 2b d1 6a 01 e8 d2 09 2c 00",
                        "eb 0c 48 8d 0d 2b d1 6a 01 e8 d2 09 2c 00"),
            ),
            'skip_import_source_data': (
                _record(0x1E3CE7, "89 82 44 01 00 00 8b d7 49 8b cf e8 e1 42 51 00",
                        "89 82 44 01 00 00 8b d7 49 8b cf 90 90 90 90 90"),
            ),
        },
    ),
    # halo2a: tool.exe
    (0x8664, 0x6595A91D, 0x55FB000): (
        'halo2a', 'tool', {
            'skip_vertex_compression': (
                _record(0x27AD48, "0f 8e e0 04 00 00 48 89 b4 24 d8 00 00 00",
                        "48 e9 e0 04 00 00 48 89 b4 24 d8 00 00 00"),
                _record(0x232E90, "0f 8e 35 0a 00 00 48 8d 47 48 48 89 45 b8",
                        "48 e9 35 0a 00 00 48 8d 47 48 48 89 45 b8"),
            ),
            'plane_builder': (
                _record(0x261F35, "77 0c 48 8d 0d 5a aa b0 01 e8 7d ff 3a 00",
                        "eb 0c 48 8d 0d 5a aa b0 01 e8 7d ff 3a 00"),
                _record(0x261FA7, "77 0c 48 8d 0d 68 aa b0 01 e8 0b ff 3a 00",
                        "eb 0c 48 8d 0d 68 aa b0 01 e8 0b ff 3a 00"),
                _record(0x262015, "77 0c 48 8d 0d 7a aa b0 01 e8 9d fe 3a 00",
                        "eb 0c 48 8d 0d 7a aa b0 01 e8 9d fe 3a 00"),
                _record(0x237F8D, "77 0c 48 8d 0d 92 a4 b1 01 e8 25 9f 3d 00",
                        "eb 0c 48 8d 0d 92 a4 b1 01 e8 25 9f 3d 00"),
                _record(0x227B44, "77 0c 48 8d 0d 1b 1f b3 01 e8 6e a3 3e 00",
                        "eb 0c 48 8d 0d 1b 1f b3 01 e8 6e a3 3e 00"),
            ),
            'skip_import_source_data': (
                _record(0x1FE919, "41 89 81 44 01 00 00 8b d7 49 8b cc e8 c6 fa 6e 00",
                        "41 89 81 44 01 00 00 8b d7 49 8b cc 90 90 90 90 90"),
            ),
        },
    ),
    # halo2a: tool_fast.exe
    (0x8664, 0x6595A9F4, 0x4D98000): (
        'halo2a', 'tool_fast', {
            'skip_vertex_compression': (
                _record(0x2B0AEC, "0f 8e f4 05 00 00 48 89 ac 24 d8 00 00 00",
                        "48 e9 f4 05 00 00 48 89 ac 24 d8 00 00 00"),
                _record(0x24DAA2, "0f 8e ce 14 00 00 49 8d 46 48 48 89 45 f0",
                        "48 e9 ce 14 00 00 49 8d 46 48 48 89 45 f0"),
            ),
            'plane_builder': (
                _record(0x2903BE, "77 0c 48 8d 0d 69 fd 70 01 e8 28 e7 28 00",
                        "eb 0c 48 8d 0d 69 fd 70 01 e8 28 e7 28 00"),
                _record(0x290430, "77 0c 48 8d 0d 0f fd 70 01 e8 b6 e6 28 00",
                        "eb 0c 48 8d 0d 0f fd 70 01 e8 b6 e6 28 00"),
                _record(0x29049E, "77 0c 48 8d 0d b9 fc 70 01 e8 48 e6 28 00",
                        "eb 0c 48 8d 0d b9 fc 70 01 e8 48 e6 28 00"),
                _record(0x2519E3, "75 0c 48 8d 0d 04 a3 73 01 e8 03 d1 2c 00",
                        "eb 0c 48 8d 0d 04 a3 73 01 e8 03 d1 2c 00"),
                _record(0x25BC74, "77 0c 48 8d 0d 33 dd 72 01 e8 72 2e 2c 00",
                        "eb 0c 48 8d 0d 33 dd 72 01 e8 72 2e 2c 00"),
            ),
            'skip_import_source_data': (
                _record(0x1E4277, "89 82 44 01 00 00 8b d7 49 8b cf e8 5d 8e 51 00",
                        "89 82 44 01 00 00 8b d7 49 8b cf 90 90 90 90 90"),
            ),
        },
    ),
}
