# Print files

**Two print projects for the H2D**, both built by `python3 tools/bambu_project.py`, brims and supports set per part
(supports only on the tray lid, worm and worm wheel), white PLA on filament 1, white PETG on filament 2:

- **`tilt_bulk_H2D.3mf`: a whole tilter at once.** 3 plates, one material each: 1 tilter boxes (PLA), 2 tilter
  gears (PLA), 3 tilter gears (PETG).
- **`tilt_parts_H2D.3mf`: one tilter part per plate**, in the order the tilter goes together. Use it to reprint a
  part when something on a bulk plate fails.
- **`tilt_controller_box_H2D.3mf`: the controller box on its own.** 1 tray and lid together (PLA), 2 tray only,
  3 lid only.


To print plate by plate from the printer: open a project in Bambu Studio, Slice all, then Send all. One file goes to the
printer and its screen picks the plate. To see what has been printed and jump to the next plate, use the private
MakerWorld copy in Bambu Handy (#52).


- [`tilter/`](tilter/README.md): every printed part of one tilter, `print/` = turned to print orientation, plus the Bambu Studio projects.
- `controller/`: controller box tray and lid, each lying the way it prints (lid top face down) ([controller box](../../../docs/controller-box.md)).
- `hub/`: the Tilt Hub box, one piece ([hub box](../../../docs/hub-box.md)).
- `plug/`: the optional wall plug for a 5/8 in cord hole, cap face down ([wall plug](../../../docs/wall-plug.md)).
- `solar/`: the solar housing for 1 to 6 panels: tray sections and an end cap, back on the bed ([solar housing](../../../docs/solar-housing.md)).
