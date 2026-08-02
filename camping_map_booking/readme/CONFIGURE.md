Replace ``static/src/img/camping_map.png`` with the site's actual map image,
then recalibrate each ``camping.map.zone``'s ``points`` field to match its
pixel dimensions - the demo zones ship with placeholder rectangles and need
to be redrawn by eye against the real image (open `/camping/map`, compare
the overlay to the photo, and adjust the polygon coordinates accordingly).
