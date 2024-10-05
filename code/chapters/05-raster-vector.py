#!/usr/bin/env python
# coding: utf-8

# # Raster-vector interactions {#sec-raster-vector}
# 
# ## Prerequisites {.unnumbered}

# In[ ]:


#| echo: false
import matplotlib.pyplot as plt
import pandas as pd
pd.options.display.max_rows = 6
pd.options.display.max_columns = 6
pd.options.display.max_colwidth = 35
plt.rcParams['figure.figsize'] = (5, 5)


# This chapter requires importing the following packages:
# <!--jn:two packages are commented out -- should these lines be removed?-->
# <!--md: yes, done-->

# In[ ]:


import os
import math
import numpy as np
import matplotlib.pyplot as plt
import shapely
import geopandas as gpd
import rasterio
import rasterio.plot
import rasterio.mask
import rasterio.features
import rasterstats


# It also relies on the following data files:

# In[ ]:


src_srtm = rasterio.open('data/srtm.tif')
src_nlcd = rasterio.open('data/nlcd.tif')
src_grain = rasterio.open('output/grain.tif')
src_elev = rasterio.open('output/elev.tif')
src_dem = rasterio.open('data/dem.tif')
zion = gpd.read_file('data/zion.gpkg')
zion_points = gpd.read_file('data/zion_points.gpkg')
cycle_hire_osm = gpd.read_file('data/cycle_hire_osm.gpkg')
us_states = gpd.read_file('data/us_states.gpkg')
nz = gpd.read_file('data/nz.gpkg')
src_nz_elev = rasterio.open('data/nz_elev.tif')


# ## Introduction
# 
# This chapter focuses on interactions between raster and vector geographic data models, both introduced in @sec-spatial-class.
# It includes four main techniques:
# 
# -   Raster cropping and masking using vector objects (@sec-raster-cropping)
# -   Extracting raster values using different types of vector data (Section @sec-raster-extraction)
# -   Raster-vector conversion (@sec-rasterization and @sec-spatial-vectorization)
# 
# These concepts are demonstrated using data from in previous chapters, to understand their potential real-world applications.
# 
# ## Raster masking and cropping {#sec-raster-cropping}
# 
# Many geographic data projects involve integrating data from many different sources, such as remote sensing images (rasters) and administrative boundaries (vectors).
# Often the extent of input raster datasets is larger than the area of interest.
# In this case raster *masking*, *cropping*, or both, are useful for unifying the spatial extent of input data (@fig-raster-crop (b) and (c), and the following two examples, illustrate the difference between masking and cropping).
# Both operations reduce object memory use and associated computational resources for subsequent analysis steps, and may be a necessary preprocessing step before creating attractive maps involving raster data.
# 
# We will use two layers to illustrate raster cropping:
# 
# -   The `srtm.tif` raster representing elevation, in meters above sea level, in south-western Utah: a **rasterio** file connection named `src_srtm` (see @fig-raster-crop (a))
# -   The `zion.gpkg` vector layer representing the Zion National Park boundaries (a `GeoDataFrame` named `zion`)
# 
# Both target and cropping objects must have the same projection.
# Since it is easier and more precise to reproject vector layers, compared to rasters, we use the following expression to reproject (@sec-reprojecting-vector-geometries) the vector layer `zion` into the CRS of the raster `src_srtm`.
# <!-- jn: maybe reference to the CRS section/chapter -->
# <!-- md: done -->

# In[ ]:


zion = zion.to_crs(src_srtm.crs)


# To mask the image, i.e., convert all pixels which do not intersect with the `zion` polygon to "No Data", we use the [`rasterio.mask.mask`](https://rasterio.readthedocs.io/en/stable/api/rasterio.mask.html#rasterio.mask.mask) function.
# 

# In[ ]:


out_image_mask, out_transform_mask = rasterio.mask.mask(
    src_srtm, 
    zion.geometry, 
    crop=False, 
    nodata=9999
)


# Note that we need to choose and specify a "No Data" value, within the valid range according to the data type.
# Since `srtm.tif` is of type `uint16` (how can we check?), we choose `9999` (a positive integer that is guaranteed not to occur in the raster).
# Also note that **rasterio** does not directly support **geopandas** data structures, so we need to pass a "collection" of **shapely** geometries: a `GeoSeries` (see above) or a `list` of **shapely** geometries (see next example) both work.
# <!-- jn: (see below) or (see above) -->
# <!-- md: thanks, this was a mistake - now corrected -->
# The output consists of two objects.
# The first one is the `out_image` array with the masked values.

# In[ ]:


out_image_mask


# The second one is a new transformation matrix `out_transform`.

# In[ ]:


out_transform_mask


# Note that masking (without cropping!) does not modify the raster extent.
# Therefore, the new transform is identical to the original (`src_srtm.transform`).
# 
# Unfortunately, the `out_image` and `out_transform` objects do not contain any information indicating that `9999` represents "No Data".
# To associate the information with the raster, we must write it to file along with the corresponding metadata.
# For example, to write the masked raster to file, we first need to modify the "No Data" setting in the metadata.

# In[ ]:


dst_kwargs = src_srtm.meta
dst_kwargs.update(nodata=9999)
dst_kwargs


# Then we can write the masked raster to file with the updated metadata object.

# In[ ]:


new_dataset = rasterio.open('output/srtm_masked.tif', 'w', **dst_kwargs)
new_dataset.write(out_image_mask)
new_dataset.close()


# Now we can re-import the raster and check that the "No Data" value is correctly set.

# In[ ]:


src_srtm_mask = rasterio.open('output/srtm_masked.tif')


# The `.meta` property contains the `nodata` entry.
# Now, any relevant operation (such as plotting, see @fig-raster-crop (b)) will take "No Data" into account.

# In[ ]:


src_srtm_mask.meta


# The related operation, cropping, reduces the raster extent to the extent of the vector layer:
# 
# -   To just crop, *without* masking, we can derive the bounding box polygon of the vector layer, and then crop using that polygon, also combined with `crop=True` (@fig-raster-crop (c))
# -   To crop *and* mask, we can use `rasterio.mask.mask`, same as above for masking, just setting `crop=True` instead of the default `crop=False` (@fig-raster-crop (d))
# 
# For the example of cropping only, the extent polygon of `zion` can be obtained as a `shapely` geometry object using the `.unary_union.envelope` property(@fig-zion-bbox).

# In[ ]:


#| label: fig-zion-bbox
#| fig-cap: Bounding box `'Polygon'` geometry of the `zion` layer
bb = zion.unary_union.envelope
bb


# The extent can now be used for masking.
# Here, we are also using the `all_touched=True` option so that pixels partially overlapping with the extent are also included in the output.

# In[ ]:


out_image_crop, out_transform_crop = rasterio.mask.mask(
    src_srtm, 
    [bb], 
    crop=True, 
    all_touched=True, 
    nodata=9999
)


# In the case of cropping, there is no particular reason to write the result to file for easier plotting, such as in the other two examples, since there are no "No Data" values (@fig-raster-crop (c)).
# 
# ::: callout-note
# As mentioned above, **rasterio** functions typically accept vector geometries in the form of `lists` of `shapely` objects. `GeoSeries` are conceptually very similar, and also accepted. However, even an individual geometry has to be in a `list`, which is why we pass `[bb]`, and not `bb`, in the above `rasterio.mask.mask` function call (the latter would raise an error).
# :::
# 
# <!-- jn: why [bb] and not bb? -->
# <!-- md: thanks, now added an explanation -->
# Finally, the third example is where we perform crop both and mask operations, using `rasterio.mask.mask` with `crop=True`.
# 
# <!-- jn: why? -->
# <!-- md: this is not documented as much as I can tell: https://rasterio.readthedocs.io/en/latest/api/rasterio.mask.html, subjectively I'd say it's because the input is a file connection, which can be either single- or multi-band, therefore to make the function behavior uniform the output is always multi-band. I'm not sure we should write that though, will be happy to hear what you think -->
# <!-- jn: maybe split the code below into two chunks and describe them separately...? -->
# <!-- md: good idea, done -->

# In[ ]:


out_image_mask_crop, out_transform_mask_crop = rasterio.mask.mask(
    src_srtm, 
    zion.geometry, 
    crop=True, 
    nodata=9999
)


# When writing the result to file, it is here crucial to update the transform and dimensions, since they were modified as a result of cropping.
# Also note that `out_image_mask_crop` is a three-dimensional array (even though it has one band in this case), so the number of rows and columns are in `.shape[1]` and `.shape[2]` (rather than `.shape[0]` and `.shape[1]`), respectively.

# In[ ]:


dst_kwargs = src_srtm.meta
dst_kwargs.update({
    'nodata': 9999,
    'transform': out_transform_mask_crop,
    'width': out_image_mask_crop.shape[2],
    'height': out_image_mask_crop.shape[1]
})
new_dataset = rasterio.open(
    'output/srtm_masked_cropped.tif', 
    'w', 
    **dst_kwargs
)
new_dataset.write(out_image_mask_crop)
new_dataset.close()


# Let's also create a file connection to the newly created file `srtm_masked_cropped.tif` in order to plot it (@fig-raster-crop (d)).

# In[ ]:


src_srtm_mask_crop = rasterio.open('output/srtm_masked_cropped.tif')
out_image_mask_crop.shape


# @fig-raster-crop shows the original raster, and the all of the masked and cropped results.

# In[ ]:


#| label: fig-raster-crop
#| fig-cap: Raster masking and cropping
#| layout-ncol: 2
#| fig-subcap: 
#| - Original
#| - Masked
#| - Cropped
#| - Masked+Cropped
# Original
fig, ax = plt.subplots(figsize=(3.5, 3.5))
rasterio.plot.show(src_srtm, ax=ax)
zion.plot(ax=ax, color='none', edgecolor='black');
# Masked
fig, ax = plt.subplots(figsize=(3.5, 3.5))
rasterio.plot.show(src_srtm_mask, ax=ax)
zion.plot(ax=ax, color='none', edgecolor='black');
# Cropped
fig, ax = plt.subplots(figsize=(3.5, 3.5))
rasterio.plot.show(out_image_crop, transform=out_transform_crop, ax=ax)
zion.plot(ax=ax, color='none', edgecolor='black');
# Masked+Cropped
fig, ax = plt.subplots(figsize=(3.5, 3.5))
rasterio.plot.show(src_srtm_mask_crop, ax=ax)
zion.plot(ax=ax, color='none', edgecolor='black');


# ## Raster extraction {#sec-raster-extraction}
# 
# Raster extraction is the process of identifying and returning the values associated with a 'target' raster at specific locations, based on a (typically vector) geographic 'selector' object.
# The reverse of raster extraction---assigning raster cell values based on vector objects---is rasterization, described in @sec-rasterization.
# 
# In the following examples, we use a package called **rasterstats**, which is specifically aimed at extracting raster values:
# 
# -   To *points* (@sec-extraction-to-points) or to *lines* (@sec-extraction-to-lines), via the [`rasterstats.point_query`](https://pythonhosted.org/rasterstats/rasterstats.html#rasterstats.point_query) function
# -   To *polygons* (@sec-extraction-to-polygons), via the [`rasterstats.zonal_stats`](https://pythonhosted.org/rasterstats/rasterstats.html#rasterstats.zonal_stats) function
# 
# ### Extraction to points {#sec-extraction-to-points}
# 
# The simplest type of raster extraction is getting the values of raster cells at specific points.
# To demonstrate extraction to points, we will use `zion_points`, which contains a sample of 30 locations within the Zion National Park (@fig-zion-points).

# In[ ]:


#| label: fig-zion-points
#| fig-cap: 30 point locations within the Zion National Park, with elevation in the background
fig, ax = plt.subplots()
rasterio.plot.show(src_srtm, ax=ax)
zion_points.plot(ax=ax, color='black');


# The following expression extracts elevation values from `srtm.tif` according to `zion_points`, using `rasterstats.point_query`.

# In[ ]:


result1 = rasterstats.point_query(
    zion_points, 
    src_srtm.read(1), 
    nodata = src_srtm.nodata, 
    affine = src_srtm.transform,
    interpolate='nearest'
)


# The first two arguments are the vector layer and the array with rastetr values. 
# The `nodata` and `affine` arguments are used to align the array values into the CRS, and to correctly treat "No Data" flags. 
# Finally, the `interpolate` argument controls the way that the cell values are asigned to the point; `interpolate='nearest'` typically makes more sense, as opposed to the other option `interpolate='bilinear'` which is the default.
# 
# Alternatively, we can pass a raster file path to `rasterstats.point_query`, in which case `nodata` and `affine` are not necessary, as the function can understand those properties from the raster file.

# In[ ]:


result2 = rasterstats.point_query(
    zion_points, 
    'data/srtm.tif',
    interpolate='nearest'
)


# <!-- jn: explain the above arguments -->
# <!-- md: done -->
# 
# The resulting object is a `list` of raster values, corresponding to `zion_points`.
# For example, here are the elevations of the first five points.

# In[ ]:


result1[:5]


# In[ ]:


result2[:5]


# To get a `GeoDataFrame` with the original points geometries (and other attributes, if any), as well as the extracted raster values, we can assign the extraction result into a new column.
# As you can see, both approaches give the same result.

# In[ ]:


zion_points['elev1'] = result1
zion_points['elev2'] = result2
zion_points


# <!-- jn: what with multilayer raster? -->
# <!-- md: good point, now added -->
# 
# The function supports extracting from just one raster band at a time.
# When passing an array, we can read the required band (as in, `.read(1)`, `.read(2)`, etc.).
# When passing a raster file path, we can set the band using the `band_num` argument (the default being `band_num=1`).
# 
# ### Extraction to lines {#sec-extraction-to-lines}
# 
# Raster extraction is also applicable with line selectors.
# The typical line extraction algorithm is to extract one value for each raster cell touched by a line.
# However, this particular approach is not recommended to obtain values along the transects, as it is hard to get the correct distance between each pair of extracted raster values.
# 
# For line extraction, a better approach is to split the line into many points (at equal distances along the line) and then extract the values for these points using the "extraction to points" technique (@sec-extraction-to-points).
# To demonstrate this, the code below creates (see @sec-vector-data for recap) `zion_transect`, a straight line going from northwest to southeast of the Zion National Park.

# In[ ]:


coords = [[-113.2, 37.45], [-112.9, 37.2]]
zion_transect = shapely.LineString(coords)
print(zion_transect)


# The utility of extracting heights from a linear selector is illustrated by imagining that you are planning a hike.
# The method demonstrated below provides an 'elevation profile' of the route (the line does not need to be straight), useful for estimating how long it will take due to long climbs.
# 
# First, we need to create a layer consisting of points along our line (`zion_transect`), at specified intervals (e.g., `250`).
# To do that, we need to transform the line into a projected CRS (so that we work with true distances, in $m$), such as UTM.
# This requires going through a `GeoSeries`, as **shapely** geometries have no CRS definition nor concept of reprojection (see @sec-vector-layer-from-scratch).

# In[ ]:


zion_transect_utm = gpd.GeoSeries(zion_transect, crs=4326).to_crs(32612)
zion_transect_utm = zion_transect_utm.iloc[0]


# The printout of the new geometry shows this is still a straight line between two points, only with coordinates in a projected CRS.

# In[ ]:


print(zion_transect_utm)


# Next, we need to calculate the distances, along the line, where points are going to be generated, using [`np.arange`](https://numpy.org/doc/stable/reference/generated/numpy.arange.html).
# This is a numeric sequence starting at `0`, going up to line `.length`, in steps of `250` ($m$).

# In[ ]:


distances = np.arange(0, zion_transect_utm.length, 250)
distances[:7]  ## First 7 distance cutoff points


# The distances cutoffs are used to sample ("interpolate") points along the line.
# The **shapely** [`.interpolate`](https://shapely.readthedocs.io/en/stable/manual.html#object.interpolate) method is used to generate the points, which then are reprojected back to the geographic CRS of the raster (EPSG:`4326`).

# In[ ]:


zion_transect_pnt = [zion_transect_utm.interpolate(distance) for distance in distances]
zion_transect_pnt = gpd.GeoSeries(zion_transect_pnt, crs=32612).to_crs(src_srtm.crs)
zion_transect_pnt


# Finally, we extract the elevation values for each point in our transect and combine the information with `zion_transect_pnt` (after "promoting" it to a `GeoDataFrame`, to accommodate extra attributes), using the point extraction method shown earlier (@sec-extraction-to-points).
# We also attach the respective distance cutoff points `distances`.

# In[ ]:


result = rasterstats.point_query(
    zion_transect_pnt, 
    src_srtm.read(1), 
    nodata = src_srtm.nodata, 
    affine = src_srtm.transform,
    interpolate='nearest'
)
zion_transect_pnt = gpd.GeoDataFrame(geometry=zion_transect_pnt)
zion_transect_pnt['dist'] = distances
zion_transect_pnt['elev'] = result
zion_transect_pnt


# The information in `zion_transect_pnt`, namely the `'dist'` and `'elev'` attributes, can now be used to draw an elevation profile, as illustrated in @fig-zion-transect.

# In[ ]:


#| label: fig-zion-transect
#| fig-cap: Extracting a raster values profile to line 
#| layout-ncol: 2
#| fig-subcap: 
#| - Raster and a line transect
#| - Extracted elevation profile
# Raster and a line transect
fig, ax = plt.subplots()
rasterio.plot.show(src_srtm, ax=ax)
gpd.GeoSeries(zion_transect).plot(ax=ax, color='black')
zion.plot(ax=ax, color='none', edgecolor='white');
# Elevation profile
fig, ax = plt.subplots()
zion_transect_pnt.set_index('dist')['elev'].plot(ax=ax)
ax.set_xlabel('Distance (m)')
ax.set_ylabel('Elevation (m)');


# ### Extraction to polygons {#sec-extraction-to-polygons}
# 
# The final type of geographic vector object for raster extraction is polygons.
# Like lines, polygons tend to return many raster values per polygon.
# For continuous rasters (@fig-raster-extract-to-polygon (a)), we typically want to generate summary statistics for raster values per polygon, for example to characterize a single region or to compare many regions.
# The generation of raster summary statistics, by polygons, is demonstrated in the code below using `rasterstats.zonal_stats`, which creates a list of summary statistics (in this case a list of length 1, since there is just one polygon).

# In[ ]:


result = rasterstats.zonal_stats(
    zion, 
    src_srtm.read(1), 
    nodata = src_srtm.nodata, 
    affine = src_srtm.transform, 
    stats = ['mean', 'min', 'max']
)
result


# ::: callout-note
# `rasterstats.zonal_stats`, just like `rasterstats.point_query` (@sec-extraction-to-points), supports raster input as file paths, rather than arrays plus `nodata` and `affine` arguments.
# :::
# 
# Transformation of the `list` to a `DataFrame` (e.g., to attach the derived attributes to the original polygon layer), is straightforward with the `pd.DataFrame` constructor.

# In[ ]:


pd.DataFrame(result)


# Because there is only one polygon in the example, a `DataFrame` with a single row is returned.
# However, if `zion` was composed of more than one polygon, we would accordingly get more rows in the `DataFrame`.
# The result provides useful summaries, for example that the maximum height in the park is around `2661` $m$ above see level.
# 
# Note the `stats` argument, where we determine what type of statistics are calculated per polygon.
# Possible values other than `'mean'`, `'min'`, `'max'` are:
# 
# -   `'count'`---The number of valid (i.e., excluding "No Data") pixels
# -   `'nodata'`---The number of pixels with 'No Data"
# -   `'majority'`---The most frequently occurring value
# -   `'median'`---The median value
# 
# See the [documentation](https://pythonhosted.org/rasterstats/manual.html#statistics) of `rasterstats.zonal_stats` for the complete list.
# Additionally, the `rasterstats.zonal_stats` function accepts user-defined functions for calculating any custom statistics.
# 
# To count occurrences of categorical raster values within polygons (@fig-raster-extract-to-polygon (b)), we can use masking (@sec-raster-cropping) combined with `np.unique`, as follows.

# In[ ]:


out_image, out_transform = rasterio.mask.mask(
    src_nlcd, 
    zion.geometry.to_crs(src_nlcd.crs), 
    crop=False, 
    nodata=9999
)
counts = np.unique(out_image, return_counts=True)
counts


# According to the result, for example, pixel value `2` ("Developed" class) appears in `4205` pixels within the Zion polygon.
# 
# @fig-raster-extract-to-polygon illustrates the two types of raster extraction to polygons described above.

# In[ ]:


#| label: fig-raster-extract-to-polygon
#| fig-cap: Sample data used for continuous and categorical raster extraction to a polygon
#| layout-ncol: 2
#| fig-subcap: 
#| - Continuous raster
#| - Categorical raster
# Continuous raster
fig, ax = plt.subplots()
rasterio.plot.show(src_srtm, ax=ax)
zion.plot(ax=ax, color='none', edgecolor='black');
# Categorical raster
fig, ax = plt.subplots()
rasterio.plot.show(src_nlcd, ax=ax, cmap='Set3')
zion.to_crs(src_nlcd.crs).plot(ax=ax, color='none', edgecolor='black');


# <!-- jn: what is the state of plotting categorical rasters? can it read the color palette from a file? -->
# <!-- md: admittedly I've never used this functionality in either R or Python... If you have a sample data file I'll be happy to experiment with it. -->
# 
# ## Rasterization {#sec-rasterization}
# 
# <!-- jn: intro is missing -->
# <!-- md: the first parts of the section are the intro, now reorganized -->
# 
# Rasterization is the conversion of vector objects into their representation in raster objects.
# Usually, the output raster is used for quantitative analysis (e.g., analysis of terrain) or modeling.
# As we saw in @sec-spatial-class, the raster data model has some characteristics that make it conducive to certain methods.
# Furthermore, the process of rasterization can help simplify datasets because the resulting values all have the same spatial resolution: rasterization can be seen as a special type of geographic data aggregation.
# 
# The **rasterio** package contains the [`rasterio.features.rasterize`](https://rasterio.readthedocs.io/en/stable/api/rasterio.features.html#rasterio.features.rasterize) function for doing this work.
# To make it happen, we need to have the "template" grid definition, i.e., the "template" raster defining the extent, resolution and CRS of the output, in the `out_shape` (the output dimensions) and `transform` (the transformation matrix) arguments of `rasterio.features.rasterize`.
# In case we have an existing template raster, we simply need to query its `.shape` and `.transform`.
# On the other hand, if we need to create a custom template, e.g., covering the vector layer extent with specified resolution, there is some extra work to calculate both of these objects (see next example).
# 
# As for the vector geometries and their associated values, the `rasterio.features.rasterize` function requires the input vector shapes in the form of an iterable object of `geometry,value` pairs, where:
# 
# -   `geometry` is the given geometry (**shapely** geometry object)
# -   `value` is the value to be "burned" into pixels coinciding with the geometry (`int` or `float`)
# 
# Furthermore, we define how to deal with multiple values burned into the same pixel, using the `merge_alg` parameter.
# The default `merge_alg=rasterio.enums.MergeAlg.replace` means that "later" values replace "earlier" ones, i.e., the pixel gets the "last" burned value.
# The other option `merge_alg=rasterio.enums.MergeAlg.add` means that burned values are summed, i.e., the pixel gets the sum of all burned values.
# 
# When rasterizing lines and polygons, we also have the choice between two pixel-matching algorithms. 
# The default, `all_touched=False`, implies pixels that are selected by [Bresenham's line algorithm](https://en.wikipedia.org/wiki/Bresenham%27s_line_algorithm) (for lines) or pixels whose center is within the polygon (for polygons).
# The other option `all_touched=True`, as the name suggests, implies that all pixels intersecting with the geometry are matched.
# 
# Finally, we can set the `fill` value, which is the value that "unaffected" pixels get, with `fill=0` being the default.
# 
# How the `rasterio.features.rasterize` function works with all of these various parameters will be made clear in the next examples.
# 
# The geographic resolution of the "template" raster has a major impact on the results: if it is too low (cell size is too large), the result may miss the full geographic variability of the vector data; if it is too high, computational times may be excessive.
# There are no simple rules to follow when deciding an appropriate geographic resolution, which is heavily dependent on the intended use of the results.
# Often the target resolution is imposed on the user, for example when the output of rasterization needs to be aligned to the existing raster.
# 
# Depending on the input data, rasterization typically takes one of two forms which we demonstrate next:
# 
# -   in *point* rasterization (@sec-rasterizing-points), we typically choose how to treat multiple points: either to summarize presence/absence, point count, or summed attribute values (@fig-rasterize-points)
# -   in *line* and *polygon* rasterization (@sec-rasterizing-lines-and-polygons), there are typically no such "overlaps" and we simply "burn" attribute values, or fixed values, into pixels coinciding with the given geometries (@fig-rasterize-lines-polygons)
# 
# ### Rasterizing points {#sec-rasterizing-points}
# 
# To demonstrate point rasterization, we will prepare a "template" raster that has the same extent and CRS as the input vector data `cycle_hire_osm_projected` (a dataset on cycle hire points in London, illustrated in @fig-rasterize-points (a)) and a spatial resolution of 1000 $m$.
# To do that, we first take our point layer and transform it to a projected CRS.

# In[ ]:


cycle_hire_osm_projected = cycle_hire_osm.to_crs(27700)


# Next, we calculate the `out_shape` and `transform` of the template raster.
# To calculate the transform, we combine the top-left corner of the `cycle_hire_osm_projected` bounding box with the required resolution (e.g., 1000 $m$).

# In[ ]:


bounds = cycle_hire_osm_projected.total_bounds
res = 1000
transform = rasterio.transform.from_origin(
    west=bounds[0], 
    north=bounds[3], 
    xsize=res, 
    ysize=res
)
transform


# To calculate the `out_shape`, we divide the x-axis and y-axis extent by the resolution, taking the ceiling of the results.

# In[ ]:


rows = math.ceil((bounds[3] - bounds[1]) / res)
cols = math.ceil((bounds[2] - bounds[0]) / res)
shape = (rows, cols)
shape


# Finally, we are ready to rasterize.
# As mentioned abover, point rasterization can be a very flexible operation: the results depend not only on the nature of the template raster, but also on the pixel "activation" method, namely the way we deal with multiple points matching the same pixel.
# 
# To illustrate this flexibility, we will try three different approaches to point rasterization (@fig-rasterize-points (b)-(d)).
# First, we create a raster representing the presence or absence of cycle hire points (known as presence/absence rasters).
# In this case, we transfer the value of `1` to all pixels where at least one point falls in.
# In the **rasterio** framework, we use the `rasterio.features.rasterize` function, which requires an iterable object of `geometry,value` pairs. 
# In this first example, we transform the point `GeoDataFrame` into a `list` of `shapely` geometries and the (fixed) value of `1`, using list comprehension as follows.
# The first five elements of the `list` are hereby printed to illustrate its structure.
# <!-- jn: maybe explain the code below in more detail? -->
# <!-- md: the code is now simplified and hopefully better explained -->
# <!-- jn: also maybe use a different name than g? -->
# <!-- md: I though 'g' for 'geometries' is OK here. 'shapes' can be confusing because there is also 'shape' in the second parameter. will be happy to hear other ideas -->

# In[ ]:


g = [(g, 1) for g in cycle_hire_osm_projected.geometry]
g[:5]


# The list of `geometry,value` pairs is passed to `rasterio.features.rasterize`, along with the `shape` and `transform` which define the raster template.
# The result `ch_raster1` is an `ndarray` with the burned values of `1` where the pixel coincides with at least one point, and `0` in "unaffected" pixels.
# Note that `merge_alg=rasterio.enums.MergeAlg.replace` (the default) is used here, which means that a pixel get `1` when one or more point fall in it, or keeps the original `0` value otherwise.
# 
# <!-- md: IMHO printing is important here to illustrate what we get in 'ch_raster1', so I've removed the 'eval:false' part -->

# In[ ]:


ch_raster1 = rasterio.features.rasterize(
    shapes=g,
    out_shape=shape, 
    transform=transform
)
ch_raster1


# In our second variant of point rasterization, we count the number of bike hire stations. 
# To do that, we use the fixed value of `1` (same as in the last example), but this time combined with the `merge_alg=rasterio.enums.MergeAlg.add` argument. 
# That way, multiple values burned into the same pixel are *summed*, rather than replaced keeping last (which is the default).
# The new output, `ch_raster2`, shows the number of cycle hire points in each grid cell.
# <!--jn: rasterio.enums.MergeAlg.add definetely needs more explanation (maybe as a block)...-->
# <!-- md: agree this required more information, the 'merge_alg' argument is now exaplained in the intro where the function is introduced -->
# <!-- md: same here, I think the array should be printed like in similar cases in the book, to show what the function returns -->

# In[ ]:


g = [(g, 1) for g in cycle_hire_osm_projected.geometry]
ch_raster2 = rasterio.features.rasterize(
    shapes=g,
    out_shape=shape,
    transform=transform,
    merge_alg=rasterio.enums.MergeAlg.add
)
ch_raster2


# The cycle hire locations have different numbers of bicycles described by the capacity variable, raising the question, what is the capacity in each grid cell?
# To calculate that, in our third point rasterization variant we sum the field (`'capacity'`) rather than the fixed values of `1`.
# This requires using a more complex list comprehension expression, where we also (1) extract both geometries and the attribute of interest, and (2) filter out "No Data" values, which can be done as follows.
# You are invited to run the separate parts to see how this works; the important point is that, in the end, we get the list `g` with the `geometry,value` pairs to be burned, only that the `value` is now variable, rather than fixed, among points.
# <!-- jn: I think the code below should be explained in more detail... -->
# <!-- md: I agree, now split into two code blocks and explained -->

# In[ ]:


g = [(g, v) for g, v in cycle_hire_osm_projected[['geometry', 'capacity']] \
        .dropna(subset='capacity')
        .to_numpy() \
        .tolist()]
g[:5]


# Now we rasterize the points, again using `merge_alg=rasterio.enums.MergeAlg.add` to sum the capacity values per pixel.

# In[ ]:


ch_raster3 = rasterio.features.rasterize(
    shapes=g,
    out_shape=shape,
    transform=transform,
    merge_alg=rasterio.enums.MergeAlg.add
)
ch_raster3


# The result `ch_raster3` shows the total capacity of cycle hire points in each grid cell.
# 
# The input point layer `cycle_hire_osm_projected` and the three variants of rasterizing it `ch_raster1`, `ch_raster2`, and `ch_raster3` are shown in @fig-rasterize-points.

# In[ ]:


#| label: fig-rasterize-points
#| fig-cap: Original data and three variants of point rasterization
#| layout-ncol: 2
#| fig-subcap: 
#| - Input points
#| - Presence/Absence
#| - Point counts
#| - Summed attribute values
# Input points
fig, ax = plt.subplots()
cycle_hire_osm_projected.plot(column='capacity', ax=ax);
# Presence/Absence
fig, ax = plt.subplots()
rasterio.plot.show(ch_raster1, transform=transform, ax=ax);
# Point counts
fig, ax = plt.subplots()
rasterio.plot.show(ch_raster2, transform=transform, ax=ax);
# Summed attribute values
fig, ax = plt.subplots()
rasterio.plot.show(ch_raster3, transform=transform, ax=ax);


# ### Rasterizing lines and polygons {#sec-rasterizing-lines-and-polygons}
# 
# Another dataset based on California's polygons and borders (created below) illustrates rasterization of lines.
# There are three preliminary steps.
# First, we subset the California polygon.

# In[ ]:


california = us_states[us_states['NAME'] == 'California']
california


# Second, we "cast" the polygon into a `'MultiLineString'` geometry, using the [`.boundary`](https://geopandas.org/en/stable/docs/reference/api/geopandas.GeoSeries.boundary.html) property that `GeoSeries` have.

# In[ ]:


california_borders = california.geometry.boundary
california_borders


# Third, we create the `transform` and `shape` describing our template raster, with a resolution of a `0.5` degree, using the same approach as in @sec-rasterizing-points.

# In[ ]:


bounds = california_borders.total_bounds
res = 0.5
transform = rasterio.transform.from_origin(
    west=bounds[0], 
    north=bounds[3], 
    xsize=res, 
    ysize=res
)
rows = math.ceil((bounds[3] - bounds[1]) / res)
cols = math.ceil((bounds[2] - bounds[0]) / res)
shape = (rows, cols)
shape


# Finally, we rasterize `california_borders` based on the calculated template's `shape` and `transform`.
# When considering line or polygon rasterization, one useful additional argument is `all_touched`.
# By default it is `False`, but when changed to `True`---all cells that are touched by a line or polygon border get a value.
# Line rasterization with `all_touched=True` is demonstrated in the code below (@fig-rasterize-lines-polygons, left).
# We are also using `fill=np.nan` to set "background" values as "No Data".

# In[ ]:


california_raster1 = rasterio.features.rasterize(
    [(g, 1) for g in california_borders],
    out_shape=shape,
    transform=transform,
    all_touched=True,
    fill=np.nan
)


# Compare it to a polygon rasterization, with `all_touched=False` (the default), which selects only raster cells whose centroids are inside the selector polygon, as illustrated in @fig-rasterize-lines-polygons (right).

# In[ ]:


california_raster2 = rasterio.features.rasterize(
    [(g, 1) for g in california.geometry],
    out_shape=shape,
    transform=transform,
    fill=np.nan
)


# To illustrate which raster pixels are actually selected as part of rasterization, we also show them as points.
# This also requires the following code section to calculate the points, which we explain in @sec-spatial-vectorization.
# 
# <!-- md: note to self that if we switch to a more efficient raster-to-points method (following Anita's suggestion), then this code block needs to be changed as well (edit: now done) -->

# In[ ]:


height = california_raster1.shape[0]
width = california_raster1.shape[1]
cols, rows = np.meshgrid(np.arange(width), np.arange(height))
x, y = rasterio.transform.xy(transform, rows, cols)
x = np.array(x).flatten()
y = np.array(y).flatten()
z = california_raster1.flatten()
geom = gpd.points_from_xy(x, y, crs=california.crs)
pnt = gpd.GeoDataFrame(data={'value':z}, geometry=geom)
pnt


# @fig-rasterize-lines-polygons shows the input vector layer, the rasterization results, and the points `pnt`.

# In[ ]:


#| label: fig-rasterize-lines-polygons
#| fig-cap: Examples of line and polygon rasterization 
#| layout-ncol: 2
#| fig-subcap: 
#| - Line rasterization w/ `all_touched=True`
#| - Polygon rasterization w/ `all_touched=False`
# Line rasterization
fig, ax = plt.subplots()
rasterio.plot.show(california_raster1, transform=transform, ax=ax, cmap='Set3')
gpd.GeoSeries(california_borders).plot(ax=ax, edgecolor='darkgrey', linewidth=1)
pnt.plot(ax=ax, color='black', markersize=1);
# Polygon rasterization
fig, ax = plt.subplots()
rasterio.plot.show(california_raster2, transform=transform, ax=ax, cmap='Set3')
california.plot(ax=ax, color='none', edgecolor='darkgrey', linewidth=1)
pnt.plot(ax=ax, color='black', markersize=1);


# ## Spatial vectorization {#sec-spatial-vectorization}
# 
# Spatial vectorization is the counterpart of rasterization (@sec-rasterization).
# It involves converting spatially continuous raster data into spatially discrete vector data such as points, lines or polygons.
# There are three standard methods to convert a raster to a vector layer, which we cover next:
# 
# -   Raster to polygons (@sec-raster-to-polygons)---converting raster cells to rectangular polygons, representing pixel areas
# -   Raster to points (@sec-raster-to-points)---converting raster cells to points, representing pixel centroids
# -   Raster to contours (@sec-raster-to-contours)
# 
# Let us demonstrate all three in the given order.
# 
# ### Raster to polygons {#sec-raster-to-polygons}
# 
# The [`rasterio.features.shapes`](https://rasterio.readthedocs.io/en/stable/api/rasterio.features.html#rasterio.features.shapes) gives access to raster pixels as polygon geometries, along with the associated raster values.
# The returned object is a generator (see note in @sec-spatial-subsetting-raster), yielding `geometry,value` pairs.
# <!-- jn: the above paragraph is not easy to read, maybe rephrase? -->
# <!-- md: right, now rephrased -->
# 
# For example, the following expression returns a generator named `shapes`, referring to the pixel polygons.

# In[ ]:


shapes = rasterio.features.shapes(
    rasterio.band(src_grain, 1) 
)
shapes


# We can generate all shapes at once into a `list` named `pol` with `list(shapes)`.

# In[ ]:


pol = list(shapes)


# Each element in `pol` is a `tuple` of length 2, containing the GeoJSON-like `dict`---representing the polygon geometry and the value of the pixel(s)---which comprise the polygon.
# For example, here is the first element of `pol`.

# In[ ]:


pol[0]


# <!-- jn: maybe the next sentence as a block -->
# <!-- md: sure, done -->
# 
# ::: callout-note
# Note that, when transforming a raster cell into a polygon, five coordinate pairs need to be kept in memory to represent  its geometry (explaining why rasters are often fast compared with vectors!).
# :::
# 
# To transform the `list` coming out of `rasterio.features.shapes` into the familiar `GeoDataFrame`, we need few more steps of data reshaping.
# First, we apply the [`shapely.geometry.shape`](https://shapely.readthedocs.io/en/stable/manual.html#shapely.geometry.shape) function to go from a `list` of GeoJSON-like `dict`s to a `list` of `shapely` geometry objects.
# The `list` can then be converted to a `GeoSeries` (see @sec-vector-layer-from-scratch).
# <!-- jn: add a sentence or two here... -->
# <!-- md: right, now split the code to several blocks and added explanations -->

# In[ ]:


geom = [shapely.geometry.shape(i[0]) for i in pol]
geom = gpd.GeoSeries(geom, crs=src_grain.crs)
geom


# The values can also be extracted from the `rasterio.features.shapes` and turned into a corresponding `Series`.

# In[ ]:


values = [i[1] for i in pol]
values = pd.Series(values)
values


# Finally, the two can be combined into a `GeoDataFrame`, hereby named `result`.

# In[ ]:


result = gpd.GeoDataFrame({'value': values, 'geometry': geom})
result


# The polygon layer `result` is shown in @fig-raster-to-polygons.

# In[ ]:


#| label: fig-raster-to-polygons
#| fig-cap: '`grain.tif` converted to a polygon layer'
result.plot(column='value', edgecolor='black', legend=True);


# As highlighted using `edgecolor='black'`, neighboring pixels sharing the same raster value are dissolved into larger polygons.
# The `rasterio.features.shapes` function unfortunately does not offer a way to avoid this type of dissolving.
# One [suggestion](https://gis.stackexchange.com/questions/455980/vectorizing-all-pixels-as-separate-polygons-using-rasterio#answer-456251) is to add unique values between `0` and `0.9999` to all pixels, convert to polygons, and then get back to the original values using [`np.floor`](https://numpy.org/doc/stable/reference/generated/numpy.floor.html).
# 
# ### Raster to points {#sec-raster-to-points}
# 
# To transform a raster to points, we can use the [`rasterio.transform.xy`](https://rasterio.readthedocs.io/en/latest/api/rasterio.transform.html#rasterio.transform.xy). 
# As the name suggests, the function accepts row and column indices, and transforms them into x- and y-coordinates (using the raster's transformation matrix).
# For example, the coordinates of the top-left pixel can be calculated passing the `(row,col)` indices of `(0,0)`.

# In[ ]:


src = rasterio.open('output/elev.tif')
rasterio.transform.xy(src.transform, 0, 0)


# ::: callout-note
# Keep in mind that the coordinates of the top-left pixel (`(-1.25, 1.25)`), as calculated in the above expression, refer to the pixel *centroid*. 
# Therefore, they are not identical to the raster origin coordinates (`(-1.5,1.5)`), as specified in the transformation matrix, which are the coordinates of the top-left edge/corner of the raster (see @fig-raster-to-points).

# In[ ]:


src.transform


# :::
# 
# To generalize the above expression to calculate the coordinates of *all* pixels, we first need to generate a grid of all possible row/column index combinations.
# This can be done using [`np.meshgrid`](https://numpy.org/doc/stable/reference/generated/numpy.meshgrid.html), as follows.

# In[ ]:


height = src.shape[0]
width = src.shape[1]
cols, rows = np.meshgrid(np.arange(width), np.arange(height))


# We now have two arrays, `rows` and `cols`, matching the shape of `elev.tif` and containing the corresponding row and column indices.

# In[ ]:


rows


# In[ ]:


cols


# These can be passed to `rasterio.transform.xy` to transform the indices into point coordinates, accordingly stored in lists of arrays `x` and `y`.

# In[ ]:


x, y = rasterio.transform.xy(src.transform, rows, cols)


# In[ ]:


x


# In[ ]:


y


# Typically we want to work with the points in the form of a `GeoDataFrame` which also holds the attribute(s) value(s) as point attributes.
# To get there, we can transform the coordinates as well as any attributes to 1-dimensional arrays, and then use methods we are already familiar with (@sec-vector-layer-from-scratch) to combine them into a `GeoDataFrame`.

# In[ ]:


x = np.array(x).flatten()
y = np.array(y).flatten()
z = src.read(1).flatten()
geom = gpd.points_from_xy(x, y, crs=src.crs)
pnt = gpd.GeoDataFrame(data={'value':z}, geometry=geom)
pnt


# This "high-level" workflow, like many other **rasterio**-based workflows covered in the book, is a commonly used one but lacking from the package itself. 
# From the user perspective, it may be a good idea to wrap the workflow into a function (e.g., `raster_to_points(src)`, returning a `GeoDataFrame`), to be re-used whenever we need it.
# 
# @fig-raster-to-points shows the input raster and the resulting point layer.

# In[ ]:


#| label: fig-raster-to-points
#| fig-cap: Raster and point representation of `elev.tif`
#| layout-ncol: 2
#| fig-subcap: 
#| - Input raster
#| - Points
# Input raster
fig, ax = plt.subplots()
pnt.plot(column='value', legend=True, ax=ax)
rasterio.plot.show(src_elev, ax=ax);
# Points
fig, ax = plt.subplots()
pnt.plot(column='value', legend=True, ax=ax)
rasterio.plot.show(src_elev, cmap='Greys', ax=ax);


# Note that "No Data" pixels can be filtered out from the conversion, if necessary (see @sec-distance-to-nearest-geometry).
# 
# ### Raster to contours {#sec-raster-to-contours}
# 
# Another common type of spatial vectorization is the creation of contour lines representing lines of continuous height or temperatures (*isotherms*), for example.
# We will use a real-world digital elevation model (DEM) because the artificial raster `elev.tif` produces parallel lines (task for the reader: verify this and explain why this happens).
# Plotting contour lines is straightforward, using the `contour=True` option of `rasterio.plot.show` (@fig-raster-contours1).

# In[ ]:


#| label: fig-raster-contours1
#| fig-cap: Displaying raster contours
fig, ax = plt.subplots()
rasterio.plot.show(src_dem, ax=ax)
rasterio.plot.show(
    src_dem, 
    ax=ax, 
    contour=True, 
    levels=np.arange(0,1200,50), 
    colors='black'
);


# Unfortunately, `rasterio` does not provide any way of extracting the contour lines in the form of a vector layer, for uses other than plotting.
# 
# There are two possible workarounds:
# 
# 1.  Using `gdal_contour` on the [command line](https://gdal.org/programs/gdal_contour.html) (see below), or through its Python interface [**osgeo**](https://gis.stackexchange.com/questions/360431/how-can-i-create-contours-from-geotiff-and-python-gdal-rasterio-etc-into-sh)
# 2.  Writing a custom function to export contour coordinates generated by, e.g., [**matplotlib**](https://www.tutorialspoint.com/how-to-get-coordinates-from-the-contour-in-matplotlib) or [**skimage**](https://gis.stackexchange.com/questions/268331/how-can-i-extract-contours-from-a-raster-with-python)
# 
# We demonstrate the first approach, using `gdal_contour`.
# Although we deviate from the Python-focused approach towards more direct interaction with GDAL, the benefit of `gdal_contour` is the proven algorithm, customized to spatial data, and with many relevant options.
# Both the `gdal_contour` program (along with other GDAL programs) and its **osgeo** Python wrapper, should already be installed on your system since GDAL is a dependency of **rasterio**.
# Using the command line pathway, generating 50 $m$ contours of the `dem.tif` file can be done as follows.

# In[ ]:


#| eval: false
os.system('gdal_contour -a elev data/dem.tif output/dem_contour.gpkg -i 50.0')


# Like all GDAL programs (also see `gdaldem` example in @sec-focal-operations), `gdal_contour` works with files.
# Here, the input is the `data/dem.tif` file and the result is exported to the `output/dem_contour.gpkg` file.
# 
# To illustrate the result, let's read the resulting `dem_contour.gpkg` layer back into the Python environment.
# Note that the layer contains an attribute named `'elev'` (as specified using `-a elev`) with the contour elevation values.

# In[ ]:


contours1 = gpd.read_file('output/dem_contour.gpkg')
contours1


# @fig-raster-contours2 shows the input raster and the resulting contour layer.

# In[ ]:


#| label: fig-raster-contours2
#| fig-cap: Contours of the `dem.tif` raster, calculated using the `gdal_contour` program
fig, ax = plt.subplots()
rasterio.plot.show(src_dem, ax=ax)
contours1.plot(ax=ax, edgecolor='black');


# ## Distance to nearest geometry {#sec-distance-to-nearest-geometry}
# 
# Calculating a raster of distances to the nearest geometry is an example of a "global" raster operation (@sec-global-operations-and-distances).
# To demonstrate it, suppose that we need to calculate a raster representing the distance to the nearest coast in New Zealand.
# This example also wraps many of the concepts introduced in this chapter and in previous chapter, such as raster aggregation (@sec-raster-agg-disagg), raster conversion to points (@sec-raster-to-points), and rasterizing points (@sec-rasterizing-points).
# 
# For the coastline, we will dissolve the New Zealand administrative division polygon layer and "extract" the boundary as a `'MultiLineString'` geometry.

# In[ ]:


coastline = gpd.GeoSeries(nz.unary_union, crs=nz.crs) \
    .to_crs(src_nz_elev.crs) \
    .boundary
coastline


# For a "template" raster, we will aggregate the New Zealand DEM, in the `nz_elev.tif` file, to 5 times coarser resolution.
# The code section below follows the aggeregation example in @sec-raster-agg-disagg.
# <!-- jn: the last sentence could be rephrased... -->
# <!-- md: the following example should be relaced to more efficient code following Anita's suggestion, afterwards will rephrase the text too (edit: now done)-->

# In[ ]:


factor = 0.2
# Reading aggregated array
r = src_nz_elev.read(1,
    out_shape=(
        int(src_nz_elev.height * factor),
        int(src_nz_elev.width * factor)
        ),
    resampling=rasterio.enums.Resampling.average
)
# Updating the transform
new_transform = src_nz_elev.transform * src_nz_elev.transform.scale(
    (src_nz_elev.width / r.shape[1]),
    (src_nz_elev.height / r.shape[0])
)


# The resulting array `r`/`new_transform` and the lines layer `coastline` are plotted in @fig-raster-distances1.
# Note that the raster values are average elevations based on $5 \times 5$ pixels, but this is irrelevant for the subsequent calculation; the raster is going to be used as a template, and all of its values will be replaced with distances to coastline (@fig-raster-distances2).

# In[ ]:


#| label: fig-raster-distances1
#| fig-cap: Template with cell IDs to calculate distance to nearest geometry

fig, ax = plt.subplots()
rasterio.plot.show(r, transform=new_transform, ax=ax)
gpd.GeoSeries(coastline).plot(ax=ax, edgecolor='black');


# To calculate the actual distances, we must convert each pixel to a vector (point) geometry.
# For this purpose, we use the technique demonstrated in @sec-raster-to-points, but we're keeping the points as a `list` of `shapely` geometries, rather than a `GeoDataFrame`, since such a list is sufficient for the subsequent calculation.

# In[ ]:


height = r.shape[0]
width = r.shape[1]
cols, rows = np.meshgrid(np.arange(width), np.arange(height))
x, y = rasterio.transform.xy(new_transform, rows, cols)
x = np.array(x).flatten()
y = np.array(y).flatten()
z = r.flatten()
x = x[~np.isnan(z)]
y = y[~np.isnan(z)]
geom = gpd.points_from_xy(x, y, crs=california.crs)
geom = list(geom)
geom[:5]


# The result `geom` is a `list` of `shapely` geometries, representing raster cell centroids (excluding `np.nan` pixels, which were filtered out).
# 
# Now we can calculate the corresponding `list` of point geometries and associated distances, using the `.distance` method from **shapely**:

# In[ ]:


distances = [(i, i.distance(coastline)) for i in geom]
distances[0]


# Finally, we rasterize (see @sec-rasterizing-points) the distances into our raster template.

# In[ ]:


image = rasterio.features.rasterize(
    distances,
    out_shape=r.shape,
    dtype=np.float_,
    transform=new_transform,
    fill=np.nan
)
image


# <!-- jn: there is a file path in the code output... can we remove it? -->
# <!-- md: interesting, I don't see it locally, but the warning appears in the online version - perhaps it's an incompatibilty between 'rasterio' and Python 3.11? -->
# 
# The final result, a raster of distances to the nearest coastline, is shown in @fig-raster-distances2.

# In[ ]:


#| label: fig-raster-distances2
#| fig-cap: Distance to nearest coastline in New Zealand
fig, ax = plt.subplots()
rasterio.plot.show(image, transform=new_transform, ax=ax)
gpd.GeoSeries(coastline).plot(ax=ax, edgecolor='black');


# ## Exercises
