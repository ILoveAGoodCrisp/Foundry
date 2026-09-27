from pathlib import Path
import bpy

class ToolPatcher:
    def __init__(self, tool_path: str | Path):
        self.tool_path = str(tool_path)

    def _normalise_patch_args(self, offsets: list[int] | int, patches: list[bytes] | bytes, originals: list[bytes] | bytes):
        if not isinstance(offsets, list):
            offsets = [offsets]

        if not isinstance(patches, list):
            patches = [patches] * len(offsets)

        if not isinstance(originals, list):
            originals = [originals] * len(offsets)

        assert len(offsets) == len(patches) == len(originals)
        return offsets, patches, originals

    def _patch_records(self, offsets: list[int] | int, patches: list[bytes] | bytes, originals: list[bytes] | bytes):
        offsets, patches, originals = self._normalise_patch_args(offsets, patches, originals)
        return list(zip(offsets, patches, originals))

    def _enabled_patch_records(self, offsets: list[int] | int, patches: list[bytes] | bytes, originals: list[bytes] | bytes, enabled: bool):
        if not bpy.context.preferences.addons[__package__].preferences.allow_tool_patches or not enabled:
            return []
        return self._patch_records(offsets, patches, originals)

    def _patch(self, offsets: list[int] | int, patches: list[bytes] | bytes, originals: list[bytes] | bytes):
        self._toggle_patch(offsets, patches, originals, True)

    def _toggle_patch(self, offsets: list[int] | int, patches: list[bytes] | bytes, originals: list[bytes] | bytes, enabled: bool):
        try:
            if not bpy.context.preferences.addons[__package__].preferences.allow_tool_patches:
                enabled = False

            offsets, patches, originals = self._normalise_patch_args(offsets, patches, originals)

            with open(self.tool_path, "r+b") as f:
                for offset, patch, original in zip(offsets, patches, originals):
                    assert len(patch) == len(original)
                    expected = original if enabled else patch
                    replacement = patch if enabled else original
                    f.seek(offset)
                    data = f.read(len(expected))
                    if data == expected:
                        f.seek(offset)
                        f.write(replacement)
        except:
            print("Failed to patch Tool")

    def reach_lightmap_color(self, return_patches=False):
        original0 = b"\xE8\x4D\x54\x29\x00"
        original1 = b"\xE8\x37\x54\x29\x00"
        original2 = b"\xE8\x1C\x54\x29\x00"
        original3 = b"\xE8\xC7\x53\x29\x00"
        original4 = b"\xE8\xB1\x53\x29\x00"
        original5 = b"\xE8\x96\x53\x29\x00"
        patch = b"\x90\x90\x90\x90\x90"
        address0 = 0xF2A02
        address1 = 0xF2A18
        address2 = 0xF2A33
        address3 = 0xF2A88
        address4 = 0xF2A9E
        address5 = 0xF2AB9
        addresses = [address0, address1, address2, address3, address4, address5]
        originals = [original0, original1, original2, original3, original4, original5]

        if return_patches:
            return self._enabled_patch_records(addresses, patch, originals, True)

        self._patch(addresses, patch, originals)

    def skip_import_source_data(self, enabled=None, return_patches=False):
        """Skip geometry import's zipped source payload, retaining file metadata.

        Match the instruction context as well as the call so kit selection does
        not depend on installation folder names. Offsets are PE file offsets.
        """
        prefs = bpy.context.preferences.addons[__package__].preferences
        if enabled is None:
            enabled = prefs.patch_tool_skip_import_source_data
        enabled = enabled and prefs.allow_tool_patches
        if return_patches and not enabled:
            return []

        # Reach, H4, H2AMP: parent_file_index store, argument setup, then
        # tag_import_add_zipped_data_for_file_using_import_path. Keep the
        # store and argument setup intact and NOP only the five-byte call.
        variants = [
            (0x270E0F, "41 89 81 44 01 00 00 e8 25 10 90 00", 5),
            (0x1FD799, "41 89 81 44 01 00 00 8b d7 49 8b cc e8 b6 67 6c 00", 5),
            (0x1FE919, "41 89 81 44 01 00 00 8b d7 49 8b cc e8 c6 fa 6e 00", 5),
        ]
        if self.tool_path.lower().endswith("_fast.exe"):
            variants = [
                # Reach inlines the function. Jump from file offset 0x1DC95B
                # to 0x1DCD05, which restores RBX before advancing the loop.
                (0x1DC954, "41 89 80 44 01 00 00 45 39 65 00 7e 12", 6),
                (0x1E3CE7, "89 82 44 01 00 00 8b d7 49 8b cf e8 e1 42 51 00", 5),
                (0x1E4277, "89 82 44 01 00 00 8b d7 49 8b cf e8 5d 8e 51 00", 5),
            ]

        matches = []
        with open(self.tool_path, "rb") as tool:
            for offset, signature, size in variants:
                original = bytes.fromhex(signature)
                replacement = bytes.fromhex("e9 a5 03 00 00 90") if size == 6 else b"\x90" * 5
                patch = original[:-size] + replacement
                tool.seek(offset)
                if tool.read(len(original)) in (original, patch):
                    matches.append((offset, patch, original))

        if len(matches) != 1:
            if not enabled and not matches:
                return
            raise RuntimeError("Unsupported Tool executable for the Skip Import Source Data patch")

        offset, patch, original = matches[0]
        if return_patches:
            return self._enabled_patch_records(offset, patch, original, enabled)
        self._toggle_patch(offset, patch, original, enabled)

    def reach_plane_builder(self, enabled=True, return_patches=False):
        patch = b"\xEB"
        if self.tool_path.lower().endswith("_fast.exe"):
            # Retain the existing vertex-index and plane-distance bypasses.
            addresses = [0x19A775, 0x19A789, 0x19A79A, 0x1A0C86]
            originals = [b"\x75", b"\x75", b"\x75", b"\x73"]
            # connected_geometry_plane_builder.cpp:967-969 checks points[0..2]
            # against original_plane. These are separate from the checks above.
            # Validate the branch, assertion descriptor and call together; only
            # change JA to JMP, keeping its existing success destination.
            addresses.extend([0x19A9B3, 0x19AA27, 0x19AA91])
            originals.extend([
                bytes.fromhex("77 1e 48 8d 0d fc 82 36 01 e8 93 d4 1e 00"),
                bytes.fromhex("77 1e 48 8d 0d 70 82 36 01 e8 1f d4 1e 00"),
                bytes.fromhex("77 0c 48 8d 0d 4e 82 36 01 e8 b5 d3 1e 00"),
            ])
            patch = [b"\xEB" + original[1:] for original in originals]
        else:
            # The standard Tool already covers the same three assertions.
            addresses = [0x220CE5, 0x220D55, 0x220DBB]
            originals = b"\x77"

        if return_patches:
            return self._enabled_patch_records(addresses, patch, originals, enabled)

        self._toggle_patch(addresses, patch, originals, enabled)

    def reach_wetness_data(self, return_patches=False):
        original0 = b"\x74"
        patch0 = b"\xEB"
        original1 = b"\x25"
        patch1 = b"\x10"
        if self.tool_path.lower().endswith("_fast.exe"):
            return [] if return_patches else None
        else:
            address0 = 0xB04F12
            address1 = 0x382557
        addresses = [address0, address1]
        patches = [patch0, patch1]
        originals = [original0, original1]

        if return_patches:
            return self._enabled_patch_records(addresses, patches, originals, True)

        self._patch(addresses, patches, originals)

    def reach_ignore_node_depth_sort(self, enabled=None, return_patches=False):
        prefs = bpy.context.preferences.addons[__package__].preferences
        if enabled is None:
            enabled = prefs.patch_tool_node_depth_sort
        if not self.tool_path.lower().endswith("_fast.exe"):
            return [] if return_patches else None

        # Reach tool_fast.exe node comparators. These patches skip the depth
        # early-outs so node sorting falls through to frame ID, then name.
        render_address = 0x1CC3B0
        render_original = b"\x8B\x14\x80\x41\xFF\xC2\x45\x2B\xCA\x75\x5B\x44\x8B\x49\x14\x44"
        render_patch = b"\x8B\x14\x80\x41\xFF\xC2\x45\x2B\xCA\x90\x90\x44\x8B\x49\x14\x44"

        animation_address = 0x1D60CB
        animation_original = b"\x8B\x41\x18\x2B\x42\x18\x75\x49\x8B\x81\xF8\x01\x00\x00\x2B\x82"
        animation_patch = b"\x8B\x41\x18\x2B\x42\x18\x90\x90\x8B\x81\xF8\x01\x00\x00\x2B\x82"

        if return_patches:
            return self._enabled_patch_records(
                [render_address, animation_address],
                [render_patch, animation_patch],
                [render_original, animation_original],
                enabled,
            )

        self._toggle_patch(
            [render_address, animation_address],
            [render_patch, animation_patch],
            [render_original, animation_original],
            enabled,
        )

    def reach_uncompressed_vertex_weights(self, enabled=None, return_patches=False):
        prefs = bpy.context.preferences.addons[__package__].preferences
        if enabled is None:
            enabled = prefs.patch_tool_uncompressed_vertex_weights
        if self.tool_path.lower().endswith("_fast.exe"):
            address = 0x21FB7F
            original = b"\x0F\x8E\x5E\x03\x00\x00"
            patch = b"\x48\xE9\x5E\x03\x00\x00"
        else:
            address = 0x2B8E6D
            original = b"\x0F\x8E\x80\x03\x00\x00"
            patch = b"\x48\xE9\x80\x03\x00\x00"

        if return_patches:
            return self._enabled_patch_records(address, patch, original, enabled)

        self._toggle_patch(address, patch, original, enabled)

    def reach_skip_vertex_compression(self, enabled=None, return_patches=False):
        prefs = bpy.context.preferences.addons[__package__].preferences
        if enabled is None:
            enabled = prefs.patch_tool_skip_vertex_compression
        if self.tool_path.lower().endswith("_fast.exe"):
            addresses = [0x1B50D0, 0x15D9AD]
            originals = [
                b"\x0F\x8E\x74\x05\x00\x00",
                b"\x0F\x8E\xCE\x06\x00\x00",
            ]
            patches = [
                b"\x48\xE9\x74\x05\x00\x00",
                b"\x48\xE9\xCE\x06\x00\x00",
            ]
        else:
            addresses = [0x2395EC, 0x1E69FD]
            originals = [
                b"\x0F\x8E\x73\x04\x00\x00",
                b"\x0F\x8E\xD1\x06\x00\x00",
            ]
            patches = [
                b"\x48\xE9\x73\x04\x00\x00",
                b"\x48\xE9\xD1\x06\x00\x00",
            ]

        if return_patches:
            return self._enabled_patch_records(addresses, patches, originals, enabled)

        self._toggle_patch(addresses, patches, originals, enabled)
