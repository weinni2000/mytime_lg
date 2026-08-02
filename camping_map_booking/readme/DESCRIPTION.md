Adds an interactive campsite map, published at ``/camping/map``, showing the
site's aerial photo with clickable zones. Each zone groups a set of rentable
pitch products (``product.template`` with ``rent_ok`` enabled); clicking a
zone lists its pitches, and clicking a pitch opens its normal product page
where the existing rental date-range configurator, add-to-cart and checkout
(from ``website_sale_renting``) take over unchanged.

Zones are managed under Sales > Configuration > Camping Map Zones, where each
zone gets a name and a polygon outline (SVG points, in the map image's own
pixel coordinates). Pitches are assigned to a zone from the product form's
"Rental prices" tab.
