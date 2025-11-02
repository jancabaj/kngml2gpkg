# Summary - QGIS Plugin knGML2GPKG Development

**Date:** 2025-10-27

## Current Status

**Plugin Location:** `/home/cabaj/.local/share/QGIS/QGIS3/profiles/cabaj/python/plugins/kngml2gpkg/`

**What Works:**
- ✓ Plugin converts 2 GML files (Register C and Register E) to 1 GPKG
- ✓ Extracts 3 layers: ParcelC, ParcelE, CadastralZoning
- ✓ Transforms from EPSG:4258 to EPSG:5514
- ✓ Uses custom QGIS transformation context (accurate coordinates)
- ✓ Applies QML styles and saves them to GPKG database
- ✓ Non-modal dialog with progress bar and log
- ✓ ParcelC and CadastralZoning work perfectly
- ✓ Coordinates are accurate when using QGIS transformation

**Current Problem:**
- ✗ **ParcelE layer has "cannot create std::vector larger than max_size()" error when opening properties**
- This error occurs ONLY when using QGIS custom transformation
- The error does NOT occur with ogr2ogr default transformation, but then coordinates are slightly off

## Root Cause

Your **custom QGIS CRS transformation** (EPSG:4258 → EPSG:5514) causes some features in ParcelE to become invalid:
- Some geometries get **infinity coordinates** after transformation
- This creates an invalid extent: `(-403278, -1267834) - (inf, inf)`
- QGIS crashes when trying to display layer properties with infinite extent

## What We've Tried

1. **Removed QML styles** - Error persisted (not a style issue)
2. **Fixed duplicate field definitions in QML** - Error persisted
3. **Used ogr2ogr instead of QGIS** - Error gone BUT coordinates slightly off
4. **Manual feature-by-feature transformation with validation** - Coordinates became off
5. **Fixed geometries before transformation** - Coordinates still off

## The Dilemma

Two options, both have problems:

**Option A: Use ogr2ogr (default PROJ transformation)**
- ✓ No vector error
- ✗ Coordinates are slightly off (doesn't use your custom transformation)

**Option B: Use QGIS API (your custom transformation)**
- ✓ Coordinates are accurate
- ✗ Vector error on ParcelE (some features become invalid)

## Key Files

**Main plugin:** `knGML2GPKG.py` - Currently uses QGIS API with custom transformation (Option B)

**Conversion method (lines 108-184):**
```python
def convert_gml_to_gpkg(self, gml_c, gml_e, output_gpkg):
    target_crs = QgsCoordinateReferenceSystem('EPSG:5514')
    transform_context = QgsProject.instance().transformContext()  # Uses custom transformation

    # For each layer: load, transform, write
    save_options.ct = QgsCoordinateTransform(layer.crs(), target_crs, transform_context)
    QgsVectorFileWriter.writeAsVectorFormatV3(layer, output_gpkg, transform_context, save_options)
```

**Styles:** `styles/kn_parcelC.qml`, `styles/kn_parcelE.qml`, `styles/kn_cadastralunit.qml` - All have correct field schema matching GPKG data

## Next Steps to Try

1. **Investigate the custom transformation itself** - Check what custom transformation parameters you have configured and why they cause infinity values

2. **Try hybrid approach** - Use QGIS transformation but detect and skip/fix only the problematic features that get infinity coordinates

3. **Check the source data** - Verify if ParcelE GML has some features with coordinates outside normal bounds that fail transformation

4. **Alternative: Accept the error** - If only properties dialog crashes but layer displays fine, maybe it's acceptable?

5. **Contact transformation source** - Understand why the custom transformation creates invalid geometries for some features

## Solution Implemented (2025-10-28)

**Root Cause Found:**
- Some ParcelE features have **CORRUPT source data** with swapped lat/lon coordinates
- Example: EP.2208139, EP.2208140, EP.42785 have X=48.x, Y=19.x instead of X=19.x, Y=48.x
- This is a **data quality issue** from the cadastral office
- When transformed, these corrupt coordinates cause infinity values or place parcels in wrong location
- When "Zoom to Layer" is used in QGIS, it zooms way out due to these corrupt parcels

**Solution:**
- Detect parcels with swapped coordinates (X > 40 and Y < 40 in EPSG:4258)
- Swap X/Y coordinates back to correct order
- Transform to EPSG:5514 using custom transformation
- Log how many parcels were fixed

**Results:**
- ✅ Uses accurate government custom transformation
- ✅ No infinity coordinate errors
- ✅ Layer properties and zoom work correctly
- ✅ All features preserved (no data loss)
- ✅ **Corrupt parcels are FIXED and placed in correct location**
- ✅ Parcels that were at (~2680000, -4177000) now correctly at (~-365000, -1268000)

**Code changes in knGML2GPKG.py:**
- Added `convert_parcele_with_fixes()` method (line 199-290)
- Detects parcels with bbox.xMinimum() > 40 and bbox.yMaximum() < 40
- Swaps all points in geometry from (X,Y) to (Y,X)
- Transforms fixed geometry to target CRS

## Technical Details

**Custom Transformation Issue:**
When using `QgsProject.instance().transformContext()`, some ParcelE features transform to infinity coordinates. Need to either:
- Fix the transformation parameters
- Filter out problematic features before transformation
- Use default PROJ transformation instead

**File to investigate:** Check QGIS profile transformation settings for EPSG:4258 → EPSG:5514
