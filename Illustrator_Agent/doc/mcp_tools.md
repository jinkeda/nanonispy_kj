# MCP Tools Reference

Quick reference for Illustrator MCP tools. Full documentation in `Illustrator_MCP/README.md`.

## Core Tool

| Tool | Description |
|------|-------------|
| `illustrator_execute_script` | Execute raw JavaScript in Illustrator |

## Document Operations (7)

| Tool | Description | Key Params |
|------|-------------|------------|
| `illustrator_create_document` | Create new document | `width`, `height`, `name` |
| `illustrator_open_document` | Open existing file | `file_path` |
| `illustrator_save_document` | Save current document | - |
| `illustrator_export_document` | Export to PNG/JPG/SVG/PDF | `file_path`, `format`, `scale` |
| `illustrator_get_document_info` | Get document properties | - |
| `illustrator_close_document` | Close document | `save` |
| `illustrator_import_image` | Import PNG/JPG image | `file_path`, `x`, `y` |

## Composite Tools (NEW & PREFERRED)

| Tool | Description | Key Params |
|------|-------------|------------|
| `illustrator_draw_formatted_text` | Text + Font + Color in one step | `content`, `x`, `y`, `font_family`, `size`, `align`, `red/green/blue` |
| `illustrator_draw_arrow` | Line + Arrowhead + Group | `x1`, `y1`, `x2`, `y2`, `arrow_size`, `stroke_width` |
| `illustrator_draw_scale_bar` | Scale bar + Label (grouped) | `x`, `y`, `width`, `label`, `font_size` |
| `illustrator_create_axis` | Axis + Ticks + Labels (grouped) | `orientation`, `x`, `y`, `length`, `tick_count`, `labels`, `axis_label` |

## Artboard Management (5)

| Tool | Description | Key Params |
|------|-------------|------------|
| `illustrator_list_artboards` | Get all artboards | - |
| `illustrator_create_artboard` | Add new artboard | `x`, `y`, `width`, `height` |
| `illustrator_delete_artboard` | Remove artboard | `index` |
| `illustrator_set_active_artboard` | Switch artboard | `index` |
| `illustrator_resize_artboard` | Change artboard size | `width`, `height` |

## Shape Tools (6)

| Tool | Description | Key Params |
|------|-------------|------------|
| `illustrator_draw_rectangle` | Draw rectangle | `x`, `y`, `width`, `height`, `corner_radius` |
| `illustrator_draw_ellipse` | Draw ellipse/circle | `x`, `y`, `width`, `height` |
| `illustrator_draw_polygon` | Draw regular polygon | `x`, `y`, `radius`, `sides` |
| `illustrator_draw_line` | Draw line | `x1`, `y1`, `x2`, `y2` |
| `illustrator_draw_path` | Draw custom path | `points[]`, `closed` |
| `illustrator_draw_star` | Draw star | `x`, `y`, `outer_radius`, `inner_radius`, `points` |

## Text Tools (4)

| Tool | Description | Key Params |
|------|-------------|------------|
| `illustrator_add_text` | Add text frame | `content`, `x`, `y`, `font_family`, `font_size` |
| `illustrator_set_text_font` | Change font | `font_family`, `font_size`, `font_style` |
| `illustrator_set_text_color` | Change text color | `red`, `green`, `blue` |
| `illustrator_get_text_content` | Get text content | - |

## Layer Tools (6)

| Tool | Description | Key Params |
|------|-------------|------------|
| `illustrator_list_layers` | List all layers | - |
| `illustrator_create_layer` | Create new layer | `name` |
| `illustrator_delete_layer` | Delete layer | `name` |
| `illustrator_set_active_layer` | Set active layer | `name` |
| `illustrator_rename_layer` | Rename layer | `old_name`, `new_name` |
| `illustrator_toggle_layer_visibility` | Show/hide layer | `name` |

## Selection Tools (10)

| Tool | Description | Key Params |
|------|-------------|------------|
| `illustrator_select_all` | Select all objects | - |
| `illustrator_deselect_all` | Clear selection | - |
| `illustrator_get_selection` | Get selection info | - |
| `illustrator_delete_selection` | Delete selected | - |
| `illustrator_move_selection` | Move selection | `delta_x`, `delta_y` |
| `illustrator_scale_selection` | Scale selection | `scale_x`, `scale_y` |
| `illustrator_rotate_selection` | Rotate selection | `angle` |
| `illustrator_select_by_name` | Select by name pattern | `pattern`, `case_sensitive` |
| `illustrator_find_objects` | List objects by type/layer | `object_type`, `layer_name` |
| `illustrator_select_on_layer` | Select all on layer | `layer_name` |

## Undo/Redo (2)

| Tool | Description | Key Params |
|------|-------------|------------|
| `illustrator_undo` | Undo last action | - |
| `illustrator_redo` | Redo last undone action | - |

## Pattern Tools (6)

| Tool | Description | Key Params |
|------|-------------|------------|
| `illustrator_create_pattern` | Create pattern swatch from selection | `name` |
| `illustrator_apply_pattern` | Fill shape with pattern | `pattern_name` |
| `illustrator_transform_pattern` | Rotate/scale pattern only | `rotate`, `scale` |
| `illustrator_set_fill_opacity` | Set fill opacity | `opacity` |
| `illustrator_apply_gradient` | Apply linear/radial gradient | `gradient_type`, `start_color`, `end_color` |
| `illustrator_list_patterns` | List pattern swatches | - |

## Font Management (2)

| Tool | Description | Key Params |
|------|-------------|------------|
| `illustrator_find_replace_font` | Global font replacement | `from_font`, `to_font` |
| `illustrator_list_document_fonts` | List fonts in document | - |

## File Import (3)

| Tool | Description | Key Params |
|------|-------------|------------|
| `illustrator_place_file` | Place linked/embedded file; optional Image Trace vectorization | `file_path`, `linked`, `trace`, `trace_preset`, `expand` |
| `illustrator_embed_placed_items` | Embed all linked items | - |
| `illustrator_update_linked_items` | Refresh from source | - |

## Styling Tools (5)

| Tool | Description | Key Params |
|------|-------------|------------|
| `illustrator_set_fill_color` | Set fill color | `red`, `green`, `blue` |
| `illustrator_set_stroke_color` | Set stroke color | `red`, `green`, `blue` |
| `illustrator_set_stroke_width` | Set stroke width | `width` |
| `illustrator_remove_fill` | Remove fill | - |
| `illustrator_remove_stroke` | Remove stroke | - |

## Arrange Tools (8)

| Tool | Description | Key Params |
|------|-------------|------------|
| `illustrator_align_objects` | Align objects | `alignment` (left/center/right/top/middle/bottom) |
| `illustrator_distribute_objects` | Distribute evenly | `distribution` (horizontal/vertical) |
| `illustrator_group_selection` | Group objects | - |
| `illustrator_ungroup_selection` | Ungroup objects | - |
| `illustrator_make_clipping_mask` | Create clipping mask | - |
| `illustrator_release_clipping_mask` | Release clipping mask | - |
| `illustrator_bring_to_front` | Bring to front | - |
| `illustrator_send_to_back` | Send to back | - |

## Effects & Gradients (7)

| Tool | Description | Key Params |
|------|-------------|------------|
| `illustrator_apply_drop_shadow` | Add drop shadow | `offset_x`, `offset_y`, `blur` |
| `illustrator_apply_blur` | Apply Gaussian blur | `radius` |
| `illustrator_apply_inner_glow` | Add inner glow | `color`, `blur` |
| `illustrator_apply_outer_glow` | Add outer glow | `color`, `blur` |
| `illustrator_clear_effects` | Remove all effects | - |
| `illustrator_apply_linear_gradient` | Linear gradient fill | `start_color`, `end_color`, `angle` |
| `illustrator_apply_radial_gradient` | Radial gradient fill | `start_color`, `end_color` |

## Object Operations (10)

| Tool | Description | Key Params |
|------|-------------|------------|
| `illustrator_duplicate_selection` | Duplicate with offset | `offset_x`, `offset_y` |
| `illustrator_copy_to_layer` | Copy to layer | `layer_name` |
| `illustrator_lock_selection` | Lock objects | - |
| `illustrator_unlock_all` | Unlock all | - |
| `illustrator_hide_selection` | Hide objects | - |
| `illustrator_show_all` | Show all hidden | - |
| `illustrator_get_object_bounds` | Get bounding box | - |
| `illustrator_rename_object` | Rename object | `name` |
| `illustrator_set_opacity` | Set transparency | `opacity` (0-100) |
| `illustrator_set_blend_mode` | Set blend mode | `mode` |

## Transform Tools (4)

| Tool | Description | Key Params |
|------|-------------|------------|
| `illustrator_reflect_selection` | Mirror objects | `axis` (horizontal/vertical) |
| `illustrator_shear_selection` | Skew objects | `angle`, `axis` |
| `illustrator_transform_each` | Transform individually | various |
| `illustrator_reset_bounding_box` | Reset bounding box | - |

## Typography (6)

| Tool | Description | Key Params |
|------|-------------|------------|
| `illustrator_create_text_on_path` | Text along path | `content` |
| `illustrator_create_area_text` | Text inside shape | `content` |
| `illustrator_convert_text_to_outlines` | Text to paths | - |
| `illustrator_set_paragraph_alignment` | Set alignment | `alignment` |
| `illustrator_set_character_spacing` | Set tracking | `spacing` |
| `illustrator_set_line_height` | Set line spacing | `height` |

## Path Operations (10)

| Tool | Description |
|------|-------------|
| `illustrator_join_paths` | Join open paths |
| `illustrator_outline_stroke` | Stroke to fill |
| `illustrator_offset_path` | Create parallel path |
| `illustrator_simplify_path` | Reduce anchors |
| `illustrator_smooth_path` | Smooth curves |
| `illustrator_reverse_path` | Reverse direction |
| `illustrator_make_compound_path` | Combine paths |
| `illustrator_release_compound_path` | Split compound |
| `illustrator_expand_appearance` | Expand effects |
| `illustrator_flatten_transparency` | Flatten transparency |

## Pathfinder Operations (8)

| Tool | Description |
|------|-------------|
| `illustrator_pathfinder_unite` | Merge shapes |
| `illustrator_pathfinder_minus_front` | Subtract front |
| `illustrator_pathfinder_minus_back` | Subtract back |
| `illustrator_pathfinder_intersect` | Keep overlap |
| `illustrator_pathfinder_exclude` | Remove overlap |
| `illustrator_pathfinder_divide` | Divide at intersections |
| `illustrator_pathfinder_trim` | Trim overlapping |
| `illustrator_pathfinder_merge` | Merge same-color |

---

## Common Patterns

### Create and Style a Shape
```
illustrator_draw_rectangle(x=100, y=100, width=50, height=30)
illustrator_set_fill_color(red=0, green=114, blue=178)
illustrator_set_stroke_width(width=1)
illustrator_set_stroke_color(red=0, green=0, blue=0)
```

### Add Styled Text
```
illustrator_add_text(content="Label", x=100, y=200, font_family="Helvetica", font_size=9)
illustrator_set_text_color(red=0, green=0, blue=0)
```

### Group and Align
```
illustrator_select_all()
illustrator_align_objects(alignment="center")
illustrator_group_selection()
illustrator_deselect_all()
```

### Export High-Resolution
```
illustrator_save_document()
illustrator_export_document(file_path="output.png", format="png", scale=4.17)
```
