# LRN/GBIF

LRN/GBIF is a QGIS plugin designed to support preliminary spatial workflows for IUCN Red List assessments, especially for plant occurrence datasets.

## Main features

- Download GBIF occurrence records using taxonomic and methodological filters.
- Resolve GBIF taxon keys from scientific names.
- Apply audit-friendly filters for coordinate quality, year range and coordinate uncertainty.
- Combine GBIF records with manually added points, CSV imports and external point layers such as shapefiles, GeoPackages and GeoJSON files.
- Select one or more point layers for AOO/EOO calculation.
- Calculate Area of Occupancy (AOO) using a configurable grid, by default 2 x 2 km.
- Calculate Extent of Occurrence (EOO) using a convex hull.
- Generate IUCN-compatible AOO/EOO spatial outputs.
- Export Point Distribution data as CSV or shapefile.
- Create audit tables for records removed by filters.
- Request an official GBIF occurrence download DOI for the GBIF records used in the analysis.

## Methodological note

The plugin provides preliminary spatial outputs to support expert review. AOO and EOO values alone do not determine an IUCN Red List category. Final assessments must follow the IUCN Red List Categories and Criteria and the current IUCN guidelines, including consideration of subcriteria, threats, population trends, uncertainty and expert judgement.

## License

This plugin is released under the GNU General Public License v3.0 or later.

## Author

Alfaro-Saiz Estrella.

Credits: Grupo de Especialistas de Especies IUCN España.
