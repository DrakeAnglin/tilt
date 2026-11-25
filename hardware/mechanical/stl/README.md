# Print files

**`tilt_project_H2D.3mf`: the print project.** One Bambu Studio project for the H2D with 21 plates: plates 1-3 print a
whole set (all PLA parts of one tilter, all PETG parts, the controller box), then one plate per part in the order the
tilter goes together. Brims and supports are already set per part (supports only on the tray lid, worm and worm wheel).
Built by `python3 tools/bambu_project.py`.

To print plate by plate from the printer: open it in Bambu Studio, Slice all, then Send all. One file goes to the
printer and its screen picks the plate. To see what has been printed and jump to the next plate, use the private
MakerWorld copy in Bambu Handy (#52).


- [`tilter/`](tilter/README.md): every printed part of one tilter, `print/` = turned to print orientation, plus the Bambu Studio projects.
- `controller/`: controller box tray and lid, each lying the way it prints (lid top face down) ([controller box](../../../docs/controller-box.md)).
- `hub/`: the Tilt Hub box, one piece ([hub box](../../../docs/hub-box.md)).
