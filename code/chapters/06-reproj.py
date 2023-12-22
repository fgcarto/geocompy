#!/usr/bin/env python
# coding: utf-8

# # Reprojecting geographic data {#sec-reproj-geo-data}
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

# In[ ]:


import shutil
import math
import numpy as np
import matplotlib.pyplot as plt
import shapely
import pyproj
import geopandas as gpd
import rasterio
import rasterio.plot
import rasterio.warp


# <!-- jn: question -- cannot we just somehow set all of these pandas options globally (for the whole book), instead of repeating them in every chapter? -->
# <!-- md: good idea, will try to check how -->
# 
# It also relies on the following data files:

# In[ ]:


src_srtm = rasterio.open('data/srtm.tif')
src_nlcd = rasterio.open('data/nlcd.tif')
zion = gpd.read_file('data/zion.gpkg')
world = gpd.read_file('data/world.gpkg')
cycle_hire_osm = gpd.read_file('data/cycle_hire_osm.gpkg')


# ## Introduction
# 
# @sec-coordinate-reference-systems-intro introduced coordinate reference systems (CRSs), with a focus on the two major types: geographic ('lon/lat', with units in degrees longitude and latitude) and projected (typically with units of meters from a datum) coordinate systems.
# This chapter builds on that knowledge and goes further.
# It demonstrates how to set and transform geographic data from one CRS to another and, furthermore, highlights specific issues that can arise due to ignoring CRSs that you should be aware of, especially if your data is stored with lon/lat coordinates.
# 
# <!-- In many projects there is no need to worry about, let alone convert between, different CRSs. -->
# <!-- jn: these two sentences do not "glue" well -->
# <!-- md: I suggest keeping just the 2nd sentence -->
# It is important to know if your data is in a projected or geographic coordinate system, and the consequences of this for geometry operations.
# However, if you know the CRS of your data and the consequences for geometry operations (covered in the next section), CRSs should just work behind the scenes: people often suddenly need to learn about CRSs when things go wrong.
# Having a clearly defined project CRS that all project data is in, plus understanding how and why to use different CRSs, can ensure that things do not go wrong.
# Furthermore, learning about coordinate systems will deepen your knowledge of geographic datasets and how to use them effectively.
# 
# This chapter teaches the fundamentals of CRSs, demonstrates the consequences of using different CRSs (including what can go wrong), and how to "reproject" datasets from one coordinate system to another.
# In the next section we introduce CRSs in Python, followed by @sec-querying-and-setting-coordinate-systems which shows how to get and set CRSs associated with spatial objects.
# @sec-geometry-operations-on-projected-and-unprojected-data demonstrates the importance of knowing what CRS your data is in with reference to a worked example of creating buffers.
# We tackle questions of when to reproject and which CRS to use in @sec-when-to-reproject and @sec-which-crs-to-use, respectively.
# Finally, we cover reprojecting vector and raster objects in @sec-reprojecting-vector-geometries and @sec-reprojecting-raster-geometries and modifying map projections in @sec-custom-map-projections.
# 
# ## Coordinate Reference Systems {#sec-coordinate-reference-systems}
# 
# Most modern geographic tools that require CRS conversions, including Python packages and desktop GIS software such as QGIS, interface with [PROJ](https://proj.org/), an open source C++ library that "transforms coordinates from one coordinate reference system (CRS) to another".
# CRSs can be described in many ways, including the following:
# 
# -   Simple, yet potentially ambiguous, statements, such as, "it's in lon/lat coordinates"
# -   Formalized, yet now outdated, 'proj-strings' such as `+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs`
# -   With an identifying 'authority:code' text string such as `EPSG:4326`
# 
# Each refers to the same thing: the 'WGS84' coordinate system that forms the basis of Global Positioning System (GPS) coordinates and many other datasets.
# But which one is correct?
# 
# The short answer is that the third way to identify CRSs is correct: `EPSG:4326` is understood by **geopandas** and **rasterio** packages covered in this book, plus many other software projects for working with geographic data including [QGIS](https://docs.qgis.org/3.22/en/docs/user_manual/working_with_projections/working_with_projections.html) and [PROJ](https://proj.org/development/quickstart.html).
# `EPSG:4326` is future-proof.
# Furthermore, although it is machine readable, unlike the proj-string representation `EPSG:4326` is short, easy to remember and highly 'findable' online (searching for `EPSG:4326` yields a dedicated page on the website [epsg.io](https://epsg.io/4326), for example).
# The more concise identifier `4326` is also understood by **geopandas** and **rasterio**, but we recommend the more explicit `AUTHORITY:CODE` representation to prevent ambiguity and to provide context.
# <!-- jn: if we recommend the more explicit representation, why do we use the shorter one in the book? I prefer the longer one, but it is open for the discussion. We need to be consistent. -->
# <!-- md: I'm not sure I see why we recommend 'AUTHORITY:CODE'. Perhaps we can simply say that it is more clear, but since EPSG is the "default" and most common authority the shorter version also works and therefore we use it in the book? -->
# 
# The longer answer is that none of the three descriptions are sufficient, and more detail is needed for unambiguous CRS handling and transformations: due to the complexity of CRSs, it is not possible to capture all relevant information about them in such short text strings.
# For this reason, the Open Geospatial Consortium (OGC, which also developed the Simple Features specification that the **geopandas** package implements) developed an open standard format for describing CRSs that is called WKT (Well Known Text).
# <!-- jn: simple features or Simple Features? We need to be consistent -- please also take a look at previous chapters... -->
# <!-- md: right. IMHO "Simple Features" is more correct, now changed in other places too -->
# This is detailed in a [100+ page document](https://portal.opengeospatial.org/files/18-010r7) that "defines the structure and content of a text string implementation of the abstract model for coordinate reference systems described in ISO 19111:2019" [@opengeospatialconsortium_wellknown_2019].
# <!-- jn: the document link is broken... -->
# <!-- md: thanks, now corrected -->
# The [WKT representation](https://en.wikipedia.org/wiki/Well-known_text_representation_of_coordinate_reference_systems) of the WGS84 CRS, which has the identifier `EPSG:4326` is as follows.
# <!-- jn: I still struggle with a decision if we should show EPSG:4326 or OGC:CRS84. I think that the latter is more correct, but the former is more common. I am open for the discussion. -->
# <!-- md: I'm not even familiar with the 'OGC:CRS84' form, so I suggest keeping 'EPSG:4326', but if 'OGC:CRS84' is more correct then I'm open to the idea too -->

# In[ ]:


crs = pyproj.CRS.from_string('EPSG:4326') # or '.from_epsg(4326)'
print(crs.to_wkt(pretty=True))


# <!-- jn: maybe it would be good to add a sentence or two explaining the about wkt representation..? -->
# <!-- md: good point, I'm not sure what are the important points to say about it - for now I've added a link to Wikipedia -->
# The output of the command shows how the CRS identifier (also known as a Spatial Reference Identifier or [SRID](https://postgis.net/workshops/postgis-intro/projection.html)) works: it is simply a look-up, providing a unique identifier associated with a more complete WKT representation of the CRS.
# This raises the question: what happens if there is a mismatch between the identifier and the longer WKT representation of a CRS?
# On this point Open Geospatial Consortium [@opengeospatialconsortium_wellknown_2019] is clear, the verbose WKT representation takes precedence over the [identifier](https://docs.opengeospatial.org/is/18-010r7/18-010r7.html#37):
# 
# > Should any attributes or values given in the cited identifier be in conflict with attributes or values given explicitly in the WKT description, the WKT values shall prevail.
# 
# The convention of referring to CRSs identifiers in the form `AUTHORITY:CODE` allows a wide range of formally defined coordinate systems to be referred to.
# The most commonly used authority in CRS identifiers is EPSG, an acronym for the European Petroleum Survey Group which published a standardized list of CRSs.
# Other authorities can be used in CRS identifiers.
# `ESRI:54030`, for example, refers to ESRI's implementation of the Robinson projection, which has the following WKT string.

# In[ ]:


crs = pyproj.CRS.from_string('ESRI:54030')
print(crs.to_wkt(pretty=True))


# WKT strings are exhaustive, detailed, and precise, allowing for unambiguous CRSs storage and transformations.
# They contain all relevant information about any given CRS, including its datum and ellipsoid, prime meridian, projection, and units.
# <!-- jn: maybe it would be good to add a sentence or two explaining the about wkt representation..? -->
# <!-- md: same as above -->
# 
# Recent PROJ versions (6+) still allow use of proj-strings to define coordinate operations, but some proj-string keys (`+nadgrids`, `+towgs84`, `+k`, `+init=epsg:`) are either no longer supported or are discouraged.
# <!-- jn: "proj4 strings" or "proj-string"? We need to be consistent -- please also take a look at previous chapters... -->
# <!-- md: agree. the proj docs seem to use 'proj-string', so I'm in favor of that -->
# Additionally, only three datums (i.e., WGS84, NAD83, and NAD27) can be directly set in proj-string.
# Longer explanations of the evolution of CRS definitions and the PROJ library can be found in [@bivand_progress_2021], Chapter 2 of [@pebesma_spatial_2022], and a [blog post by Floris Vanderhaeghe](https://inbo.github.io/tutorials/tutorials/spatial_crs_coding/).
# 
# ::: callout-note
# As outlined in the [PROJ documentation](https://proj.org/development/reference/cpp/cpp_general.html), there are different versions of the WKT CRS format including WKT1 and two variants of WKT2, the latter of which (WKT2, 2018 specification) corresponds to the ISO 19111:2019 [@opengeospatialconsortium_wellknown_2019].
# :::
# <!-- jn: maybe the last sentence could be a block? -->
# <!-- md: agree, now added -->
# 
# ## Querying and setting coordinate systems {#sec-querying-and-setting-coordinate-systems}
# 
# Let's see how CRSs are stored in Python spatial objects and how they can be queried and set.
# First we will look at getting and setting CRSs in vector geographic data objects.
# Consider the `GeoDataFrame` object named `world`, imported from a file `world.gpkg` that represents countries worldwide.
# Its CRS can be retrieved using the `.crs` property.

# In[ ]:


world.crs


# The output specifies the following pieces of information:
# 
# 1.  The CRS type (`Geographic 2D CRS`) and SRID code (`EPSG:4326`)
# 2.  The CRS name (`WGS 84`)
# 3.  The axes (`latitude`, `longitude`) and their units (`degree`)
# 4.  The applicable area name (`World`) and bounding box (`(-180.0, -90.0, 180.0, 90.0)`)
# 5.  The datum (`WGS 84`)
# 
# The WKT representation, which is internally used when saving the object to a file or doing any coordinate operations, can be extracted using `.crs.to_wkt()` as shown above (@sec-coordinate-reference-systems).
# We can also see that the `world` object has the WGS84 ellipsoid, the latitude and longitude axis order, and uses the Greenwich prime meridian.
# We also have the suitable suitable area specification for the use of this CRS, and CRS identifier: `EPSG:4326`.
# 
# The CRS specification object, such as `world.crs`, has several useful properties and methods to explicitly retrieve information about the used CRS.
# For example, we can check whether the CRS is geographic with the `.is_geographic` property.

# In[ ]:


world.crs.is_geographic


# CRS units of both axes (typically identical) can be retrieved with the `.axis_info` property.

# In[ ]:


world.crs.axis_info[0].unit_name
world.crs.axis_info[1].unit_name


# `AUTHORITY` and `CODE` strings may be obtained with the `.to_authority()` method.

# In[ ]:


world.crs.to_authority()


# <!-- The `to_proj4()` method returns the proj-string representation of the CRS. -->
# <!-- world.crs.to_proj4() -->
# 
# <!-- jn: the last code example leaves the following message (I think we should either remove the whole code example, or just remove the message but explaining it in the text..): '/home/jn/micromamba/envs/geocompy/lib/python3.11/site-packages/pyproj/crs/crs.py:1293: UserWarning: You will likely lose important projection information when converting to a PROJ string from another format. See: https://proj.org/faq.html#what-is-the-best-format-for-describing-coordinate-reference-systems proj = self._crs.to_proj4(version=version)' -->
# <!-- md: I suggest in general we keep the warning messages (if any), so the reader is not surprised when they run the code. in this case, since we also mention that proj-strings are outdated, I agree we can just remove the code example -->
# 
# In cases when a coordinate reference system (CRS) is missing or the wrong CRS is set, the `.set_crs` method can be used on a `GeoSeries` or a `GeoDataFrame` to set it.
# The CRS can be specified using an EPSG code as the first argument.
# In case the object already has a different CRS definition, we must also specify `allow_override=True` to replace it (otherwise we get an error).
# In the first example we set the `EPSG:4326` CRS, which has no effect because `world` already has that exact CRS definition, while the second example replaces the existing CRS with a new definition of `EPSG:3857`.

# In[ ]:


world2 = world.set_crs(4326)
world3 = world.set_crs(3857, allow_override=True)


# The provided number is interpreted as an `EPSG` code.
# We can also use strings, as in `'EPSG:4326'`, which is useful to make the code more clear and when using other authorities than `EPSG`.

# In[ ]:


world4 = world.set_crs('ESRI:54009', allow_override=True)


# In **rasterio**, the CRS information is stored as part of a raster file connection metadata (@sec-using-rasterio).
# Replacing the CRS definition for a **rasterio** file connection is typically not necessary, because it is not considered in any operation; only the transformation matrix and coordinates are.
# One exception is when writing the raster, in which case we need to construct the metadata of the raster file to be written, and therein specify the CRS anyway (@sec-raster-from-scratch).
# However, if we, for some reason, need to change the CRS definition in the file connection metadata, we can do that when opening the file in `r+` (reading and writing) mode.
# <!-- jn: what's the difference between `r+` and `rw`? -->
# <!-- md: good point, I've added a note about file connection modes -->
# To demonstrate, we will create a copy of the `nlcd.tif` file, named `nlcd2.tif`, 

# In[ ]:


shutil.copy('data/nlcd.tif', 'output/nlcd_modified_crs.tif')


# and examine its existing CRS.

# In[ ]:


src_nlcd2 = rasterio.open('output/nlcd_modified_crs.tif', 'r+')
src_nlcd2.crs


# ::: callout-note
# The `rasterio.open` function `mode`s generally follows Python's standard [file connection](https://docs.python.org/3/tutorial/inputoutput.html#reading-and-writing-files) modes, with possible arguments being `'r'` (read), `'w'` (write), `'r+'` (read/write), and `'w+'` (write/read) (the `'a'` "append" mode is irrelevant for raster files). In the book, and in general, the most commonly used modes are `'r'` (read) and `'w'` (write). `'r+'`, used in the last example, means 'read/write'. Unlike with `'w'`, `'r+'` does not delete the existing content on open, making `'r+'` suitable for making changes in an existing file (such as in the last example, where we replaced the CRS).
# :::
# 
# To replace the definition with a new one, such as `EPSG:3857`, we can use the `.crs` method, as shown below.

# In[ ]:


src_nlcd2.crs = 3857
src_nlcd2.close()


# Next, examining the file connection demonstrates that the CRS was indeed changed.

# In[ ]:


rasterio.open('output/nlcd_modified_crs.tif').crs


# Importantly, the `.set_crs` (for vector layers) or the assignment to `.crs` (for rasters), as shown above, do not alter coordinates' values or geometries.
# Their role is only to set a metadata information about the object CRS.
# Consequently, the objects we created, `world3`, `world4`, and `src_nlcd2` are "incorrect", in the sense that the geometries are in fact given in a different CRS than specified in the associated CRS definition.
# 
# In some cases, the CRS of a geographic object is unknown, as is the case in the London dataset created in the code chunk below, building on the example of London introduced in @sec-vector-layer-from-scratch.

# In[ ]:


lnd_point = shapely.Point(-0.1, 51.5)
lnd_geom = gpd.GeoSeries([lnd_point])
lnd_layer = gpd.GeoDataFrame({'geometry': lnd_geom})
lnd_layer


# Querying the `.crs` of such a layer returns `None`, therefore nothing is printed.

# In[ ]:


lnd_layer.crs


# This implies that **geopandas** does not know what the CRS is and is unwilling to guess.
# Unless a CRS is manually specified or is loaded from a source that has CRS metadata, **geopandas** does not make any explicit assumptions about which coordinate systems, other than to say "I don't know".
# This behavior makes sense given the diversity of available CRSs but differs from some approaches, such as the GeoJSON file format specification, which makes the simplifying [assumption](https://datatracker.ietf.org/doc/html/rfc7946#section-4) that all coordinates have a lon/lat CRS: `EPSG:4326`.
# <!-- jn: Michael, please check if the above statement is still correct (I vaguely recall some recent discussion about this...)  -->
# <!-- md: as far as I can tell it's correct, now added a reference; e.g., reading a GeoJSON in 'geopandas' automatically sets CRS to 4326 -->
# 
# A CRS can be added to `GeoSeries` or `GeoDataFrame` objects using the `.set_crs` method, as mentioned above.

# In[ ]:


lnd_layer = lnd_layer.set_crs(4326)


# <!-- jn: "all geographic coordinates have a coordinate system" what does it mean? -->
# <!-- md: I'm not sure either, suggest removing the sentence -->
# <!-- In general, all geographic coordinates have a coordinate system and software can only make good decisions about plotting and geometry operations if it knows what type of CRS it is working with. -->
# When working with **geopandas** and **rasterio**, datasets without a specified CRS are not an issue in most workflows, since only the coordinates are considered.
# It is up to the user to make sure that, when working with more than one layer, all of the coordinates are given in the same CRS (whether specified or not).
# When exporting the results, though, it is important to keep the CRS definition in place, because other software typically *do* use, and require, the CRS definition in calculation.
# It should also be mentioned that, in some cases the CRS specification is left unspecified on purpose, for example when working with layers in arbitrary or non-geographic space (simulations, internal building plans, analysis of plot-scale ecological patterns, etc.).
# 
# ## Geometry operations on projected and unprojected data {#sec-geometry-operations-on-projected-and-unprojected-data}
# 
# The **geopandas** package, through its dependency **shapely**, assumes planar geometry and works with distance/area values assumed to be in CRS units.
# In fact, the CRS definition is typically ignored, and the respective functions (such as in plotting and distance calculations) are applied on the "bare" **shapely** geometries.
# Accordingly, it is crucial to make sure that:
# 
# -   Geometric calculations are only applied in projected CRS
# -   If there is more than one layer involved---all layers have to be in the same (projected) CRS
# -   Distance and area values, are passed, and returned, in CRS units
# 
# For example, to calculate a buffer of 100 $km$ around London, we need to work with a layer representing London in a projected CRS (e.g., `EPSG:27700`) and pass the distance value in the CRS units (e.g., `100000` $m$).
# 
# In the following code chunk we create, from scratch, a point layer `lnd_layer_proj` with a point representing London (compare it to `lnd_layer`, in a geographical CRS which we created above, see @sec-querying-and-setting-coordinate-systems).

# In[ ]:


lnd_point_proj = shapely.Point(530000, 180000)
lnd_geom_proj = gpd.GeoSeries([lnd_point_proj], crs=27700)
lnd_layer_proj = gpd.GeoDataFrame({'geometry': lnd_geom_proj})
lnd_layer_proj


# Now, we can use the `.buffer` method (@sec-buffers) to calculate the buffer of 100 $km$ around London.

# In[ ]:


lnd_layer_proj_buff = lnd_layer_proj.buffer(100000)
lnd_layer_proj_buff


# The resulting buffer is shown in the left panel of @fig-reprojection-geo-proj.
# 
# Calculating a 100-$km$ buffer directly for `lnd_layer`, which is in a geographical CRS, is impossible.
# Since the `lnd_layer` is in decimal degrees, the closest thing to a 100-$km$ buffer would be to use a distance of 1 degree, which is roughly equivalent to 100 $km$ (1 degree is about 111 $km$ at the equator):

# In[ ]:


lnd_layer_buff = lnd_layer.buffer(1)
lnd_layer_buff


# However, this is incorrect, as told by the warning message and shown in the right panel of @fig-reprojection-geo-proj.
# The association between degrees and true distance varies over the surface of the earth and we cannot assume it is fixed.

# In[ ]:


#| label: fig-reprojection-geo-proj
#| fig-cap: Buffers around London
#| layout-ncol: 2
#| fig-subcap:
#| - Around a projected point and distance of 100 $km$
#| - Around a point in lon/lat using distance of 1 degree (incorrectly approximating 100 $km$)
uk = world[world['name_long'] == 'United Kingdom']
uk_proj = uk.to_crs(27700)
# Around projected point
base = uk_proj.plot(color='none', edgecolor='darkgrey')
lnd_layer_proj_buff.plot(color='lightgrey', edgecolor='black', ax=base)
lnd_layer_proj.plot(color='red', ax=base);
# Around point in lon/lat
base = uk.plot(color='none', edgecolor='darkgrey')
lnd_layer_buff.plot(color='lightgrey', edgecolor='black', ax=base)
lnd_layer.plot(color='red', ax=base);


# ::: callout-note
# The distance between two lines of longitude, called meridians, is around 111 $km$ at the equator (execute `import geopy.distance;geopy.distance.geodesic((0,0),(0,1))` to find the precise distance).
# This shrinks to zero at the poles.
# At the latitude of London, for example, meridians are less than 70 $km$ apart (challenge: execute code that verifies this).
# Lines of latitude, by contrast, are equidistant from each other irrespective of latitude: they are always around 111 $km$ apart, including at the equator and near the poles.
# :::
# 
# ::: callout-note
# The [**spherely**](https://github.com/benbovy/spherely) package, which is in early stages of development, is aimed at providing a spherical-geometry counterpart to **shapely**, so that true distances (in $m$) and areas (in $m^2$) can be directly calculated on geometries in geographic CRS.
# :::
# 
# ## When to reproject? {#sec-when-to-reproject}
# 
# The previous section showed how to set the CRS manually, with an expression such as `lnd_layer.set_crs(4326)`.
# In real world applications, however, CRSs are usually set automatically when data is read-in.
# Thus, in many projects the main CRS-related task is to transform objects, from one CRS into another.
# But when should data be transformed?
# And into which CRS?
# There are no clear-cut answers to these questions and CRS selection always involves trade-offs [@maling_coordinate_1992].
# However, there are some general principles provided in this section that can help you decide.
# 
# First, it's worth considering when to transform.
# In some cases transformation to a geographic CRS is essential, such as when publishing data online (for example, a Leaflet-based map using Python package [**folium**](https://python-visualization.github.io/folium/latest/)).
# Another case is when two objects with different CRSs must be compared or combined, as shown when we try to find the distance between two objects with different CRSs.

# In[ ]:


lnd_layer.distance(lnd_layer_proj)


# Here, we got a meaningless result, and a warning.
# 
# To make the `lnd_layer` and `lnd_layer_proj` objects geographically comparable, one of them must be transformed into the CRS of the other.
# But which CRS to use?
# The answer depends on context: many projects, especially those involving web mapping, require outputs in `EPSG:4326`, in which case it is worth transforming the projected object.
# If, however, the project requires geometric calculations, implying planar geometry, e.g., calculating buffers (@sec-geometry-operations-on-projected-and-unprojected-data), it is necessary to transform data with a geographic CRS into an equivalent object with a projected CRS, such as the British National Grid (`EPSG:27700`).
# That is the subject of @sec-which-crs-to-use.
# <!-- jn: is the above cross-reference correct? does not seem to be... -->
# <!-- md: right, this was a mistake. now corrected -->
# 
# ## Which CRS to use? {#sec-which-crs-to-use}
# 
# The question of which CRS is tricky, and there is rarely a "right" answer: "There exist no all-purpose projections, all involve distortion when far from the center of the specified frame" [@bivand_applied_2013].
# Additionally, you should not be attached just to one projection for every task.
# It is possible to use one projection for some part of the analysis, another projection for a different part, and even some other for visualization.
# Always try to pick the CRS that serves your goal best!
# 
# When selecting *geographic* CRSs, the answer is often [WGS84](https://en.wikipedia.org/wiki/World_Geodetic_System#A_new_World_Geodetic_System:_WGS_84).
# It is used not only for web mapping, but also because GPS datasets and thousands of raster and vector datasets are provided in this CRS by default.
# WGS84 is the most common CRS in the world, so it is worth knowing its EPSG code: `4326`.
# This "magic number" can be used to convert objects with unusual projected CRSs into something that is widely understood.
# 
# What about when a *projected* CRS is required?
# In some cases, it is not something that we are free to decide: "often the choice of projection is made by a public mapping agency" [@bivand_applied_2013].
# This means that when working with local data sources, it is likely preferable to work with the CRS in which the data was provided, to ensure compatibility, even if the official CRS is not the most accurate.
# The example of London was easy to answer because the British National Grid (with its associated EPSG code `27700`) is well known, and the original dataset (`lnd_layer`) already had that CRS.
# 
# A commonly used default is Universal Transverse Mercator ([UTM](https://en.wikipedia.org/wiki/Universal_Transverse_Mercator_coordinate_system)), a set of CRSs that divides the Earth into 60 longitudinal wedges and 20 latitudinal segments.
# The transverse Mercator projection used by UTM CRSs is conformal but distorts areas and distances with increasing severity with distance from the center of the UTM zone.
# Documentation from the GIS software Manifold therefore suggests restricting the longitudinal extent of projects using UTM zones to 6 degrees from the central meridian (source: [manifold.net](http://www.manifold.net/doc/mfd9/universal_transverse_mercator_projection.htm)).
# Therefore, we recommend using UTM only when your focus is on preserving angles for a relatively small area!
# 
# Almost every place on Earth has a UTM code, such as `'60H'` which refers, amoung others, to northern New Zealand.
# UTM EPSG codes run sequentially from `32601` to `32660` for northern hemisphere locations and from `32701` to `32760` for southern hemisphere locations.
# 
# To show how the system works, let's create a function, `lonlat2UTM` to calculate the EPSG code associated with any point on the planet.

# In[ ]:


def lonlat2UTM(lon, lat):
    utm = (math.floor((lon + 180) / 6) % 60) + 1
    if lat > 0:
        utm += 32600
    else:
        utm += 32700
    return utm


# The following command uses this function to identify the UTM zone and associated EPSG code for Auckland.

# In[ ]:


lonlat2UTM(174.7, -36.9)


# Here is another example for London (where we "unpack" the coordinates of the 1^st^ geometry in `lnd_layer` into the `lonlat2UTM` function arguments).

# In[ ]:


lonlat2UTM(*lnd_layer.geometry.iloc[0].coords[0])


# Currently, we also have tools helping us to select a proper CRS.
# For example, the webpage <https://crs-explorer.proj.org/> lists CRSs based on selected location and type.
# Important note: while these tools are helpful in many situations, you need to be aware of the properties of the recommended CRS before you apply it.
# 
# In cases where an appropriate CRS is not immediately clear, the choice of CRS should depend on the properties that are most important to preserve in the subsequent maps and analysis.
# All CRSs are either equal-area, equidistant, conformal (with shapes remaining unchanged), or some combination of compromises of those (@sec-projected-coordinate-reference-systems).
# Custom CRSs with local parameters can be created for a region of interest and multiple CRSs can be used in projects when no single CRS suits all tasks.
# "Geodesic calculations" can provide a fall-back if no CRSs are appropriate (see <https://proj.org/geodesic.html>).
# Regardless of the projected CRS used, the results may not be accurate for geometries covering hundreds of kilometers.
# 
# When deciding on a custom CRS, we recommend the following:
# 
# -   A Lambert azimuthal equal-area ([LAEA](https://en.wikipedia.org/wiki/Lambert_azimuthal_equal-area_projection)) projection for a custom local projection (set latitude and longitude of origin to the center of the study area), which is an equal-area projection at all locations but distorts shapes beyond thousands of kilometers
# -   Azimuthal equidistant ([AEQD](https://en.wikipedia.org/wiki/Azimuthal_equidistant_projection)) projections for a specifically accurate straight-line distance between a point and the center point of the local projection
# -   Lambert conformal conic ([LCC](https://en.wikipedia.org/wiki/Lambert_conformal_conic_projection)) projections for regions covering thousands of kilometers, with the cone set to keep distance and area properties reasonable between the secant lines
# -   Stereographic ([STERE](https://en.wikipedia.org/wiki/Stereographic_projection)) projections for polar regions, but taking care not to rely on area and distance calculations thousands of kilometers from the center
# 
# One possible approach to automatically select a projected CRS specific to a local dataset is to create an azimuthal equidistant (AEQD) projection for the center-point of the study area.
# This involves creating a custom CRS (with no EPSG code) with units of meters based on the center point of a dataset.
# Note that this approach should be used with caution: no other datasets will be compatible with the custom CRS created and results may not be accurate when used on extensive datasets covering hundreds of kilometers.
# 
# The principles outlined in this section apply equally to vector and raster datasets.
# Some features of CRS transformation however are unique to each geographic data model.
# We will cover the particularities of vector data transformation in @sec-reprojecting-vector-geometries and those of raster transformation in @sec-reprojecting-raster-geometries.
# The last section, @sec-custom-map-projections, shows how to create custom map projections.
# 
# ## Reprojecting vector geometries {#sec-reprojecting-vector-geometries}
# 
# @sec-vector-data demonstrated how vector geometries are made-up of points, and how points form the basis of more complex objects such as lines and polygons.
# Reprojecting vectors thus consists of transforming the coordinates of these points, which form the vertices of lines and polygons.
# 
# @sec-geometry-operations-on-projected-and-unprojected-data contains an example in which at a `GeoDataFrame` had to be transformed into an equivalent object, with a different CRS, to calculate the distance between two objects. 
# Reprojection of vector layers is done using the [.to_crs](https://geopandas.org/en/stable/docs/reference/api/geopandas.GeoDataFrame.to_crs.html) method.

# In[ ]:


lnd_layer2 = lnd_layer.to_crs(27700)


# Now that a transformed version of `lnd_layer` has been created, the distance between the two representations of London can be found using the `.distance` method.

# In[ ]:


lnd_layer2.distance(lnd_layer_proj)


# It may come as a surprise that `lnd_layer` and `lnd_layer2` are just over 2 $km$ apart!
# The difference in location between the two points is not due to imperfections in the transforming operation (which is in fact very accurate) but the low precision of the manually-created coordinates that created `lnd_layer` and `lnd_layer_proj`.
# 
# <!-- jn: maybe we can remove the text from here to my next comment, as it is already explained in the previous section..? -->
# <!-- md: agree, now removed -->
# <!-- The CRS of `GeoSeries` and `GeoDataFrame` objects can be queried and set---as we learned in @sec-querying-and-setting-coordinate-systems---using the `.crs` property and the `.set_crs` method, respectively. -->
# <!-- The output is printed as multiple lines of text containing information about the coordinate system: -->
# 
# <!-- crs_lnd = lnd_layer.crs -->
# <!-- crs_lnd -->
# 
# <!-- As mentioned in @sec-coordinate-reference-systems, a CRS object has many useful properties to examing the CRS characteristics and details, including `.name` and `.to_epsg()`: -->
# 
# <!-- crs_lnd.name -->
# <!-- crs_lnd.to_proj4() -->
# <!-- crs_lnd.to_epsg() -->
# 
# <!-- As mentioned in @sec-coordinate-reference-systems, WKT representation, accessible through `.to_wkt()` of the `crs_lnd` object is the ultimate source of truth. -->
# <!-- This means that the outputs of the previous code chunk are queries from the WKT representation provided by PROJ, rather than inherent attributes of the object and its CRS. -->
# 
# Reprojecting to a different CRS is also demonstrated below using `cycle_hire_osm`, a point layer that represents 'docking stations' where you can hire bicycles in London.
# The contents of the CRS object associated with a given geometry column is changed when the object's CRS is transformed.
# In the code chunk below, we create a new version of `cycle_hire_osm` with a projected CRS.

# In[ ]:


cycle_hire_osm_projected = cycle_hire_osm.to_crs(27700)
cycle_hire_osm_projected.crs


# The resulting object has a new CRS with an EPSG code `27700`.
# But how to find out more details about this EPSG code, or any code?
# One option is to search for it online.
# Another option is to create a standalone CRS object within the Python environment (using `pyproj.CRS.from_string` or `pyproj.CRS.from_epsg`, see @sec-coordinate-reference-systems), and then query its properties, such as `.name` and `.to_wkt()`.

# In[ ]:


crs_lnd_new = pyproj.CRS.from_epsg(27700)
crs_lnd_new.name, crs_lnd_new.to_wkt()


# <!-- jn: what to do with the long message: '/home/jn/micromamba/envs/geocompy/lib/python3.11/site-packages/pyproj/crs/crs.py:1293: UserWarning: You will likely lose important projection information when converting to a PROJ string from another format. See: https://proj.org/faq.html#what-is-the-best-format-for-describing-coordinate-reference-systems proj = self._crs.to_proj4(version=version)' ? -->
# <!-- md: same as above, removed the code example -->
#   
# The result shows that the EPSG code `27700` represents the British National Grid, a result that could have been found by searching online for "[EPSG 27700](https://www.google.com/search?q=CRS+27700)".
# 
# ## Reprojecting raster geometries {#sec-reprojecting-raster-geometries}
# 
# The CRSs concepts described in the previous section apply equally to rasters.
# However, there are important differences in reprojection of vectors and rasters: transforming a vector object involves changing the coordinates of every vertex, but this does not apply to raster data.
# Rasters are composed of rectangular cells of the same size (expressed by map units, such as degrees or meters), so it is usually impracticable to transform coordinates of pixels separately.
# Raster reprojection involves creating a new raster object in the destination CRS, often with a different number of columns and rows than the original.
# The attributes must subsequently be re-estimated, allowing the new pixels to be "filled" with appropriate values.
# In other words, raster reprojection can be thought of as two separate spatial operations: a vector reprojection of the raster extent to another CRS (@sec-reprojecting-vector-geometries), and computation of new pixel values through resampling (@sec-raster-resampling).
# Due to this additional complexity, in most cases when both raster and vector data are used, it is better to avoid reprojecting rasters and reproject vectors instead.
# 
# ::: callout-note
# Reprojection of the regular rasters is also known as warping.
# Additionally, there is a second similar operation called "transformation".
# Instead of resampling all of the values, it leaves all values intact but recomputes new coordinates for every raster cell, changing the grid geometry.
# For example, it could convert the input raster (a regular grid) into a curvilinear grid.
# The **rasterio**, like common raster file formats (such as GeoTIFF), does not support curvilinear grids.
# The **xarray** package, for instance, can be used to [work with](https://docs.xarray.dev/en/stable/examples/multidimensional-coords.html) curvilinear grids.
# :::
# <!-- jn: regarding above note: is there any Python package supporting curvilinear grids? if yes, maybe mention it there... -->
# <!-- md: good point, added -->
# 
# The raster reprojection process is done using two functions from the `rasterio.warp` sub-package:
# 
# 1. `rasterio.warp.calculate_default_transform`: [`calculate_default_transform`](https://rasterio.readthedocs.io/en/latest/api/rasterio.warp.html#rasterio.warp.calculate_default_transform), is used to calculate the new transformation matrix in the destination CRS, according to the source raster dimensions and bounds.
# Alternatively, the destination transformation matrix can be obtained from an existing raster; this is common practice when we need to align one raster with another, for instance to be able to combine them in raster algebra operations (@sec-raster-local-operations) (see below)
# 2. `rasterio.warp.reproject`: introduced in @sec-raster-resampling, calculates cell values in the destination grid, using the user-selected resampling method (such as nearest neighbor, or bilinear)
# 
# Let's take a look at two examples of raster transformation: using categorical and continuous data.
# Land cover data are usually represented by categorical maps.
# The `nlcd.tif` file provides information for a small area in Utah, USA obtained from National Land Cover Database 2011 in the NAD83 / UTM zone 12N CRS.
# We already created a connection to the `nlcd.tif` file at the beginning of this chapter, named `src_nlcd`.

# In[ ]:


src_nlcd


# Recall from previous chapters that the raster transformation matrix and dimensions are accessible from the file connection using `src_nlcd.transform`, `src_nlcd.width`, and `src_nlcd.height`, respectively.
# <!--src_nlcd.bounds is not mentioned here but it is used in the code chunk below... -->
# 
# This information will be required to calculate the destination transformation matrix.
# 
# First, let's define the destination CRS.
# In this case, we choose WGS84 (EPSG code `4326`).

# In[ ]:


dst_crs = 'EPSG:4326'


# Now, we are ready to calculate the destination raster transformation matrix (`dst_transform`), and the destination dimensions (`dst_width`, `dst_height`), using `rasterio.warp.calculate_default_transform`, as follows:

# In[ ]:


dst_transform, dst_width, dst_height = rasterio.warp.calculate_default_transform(
    src_nlcd.crs,
    dst_crs,
    src_nlcd.width,
    src_nlcd.height,
    *src_nlcd.bounds
)
dst_transform


# In[ ]:


dst_width


# In[ ]:


dst_height


# <!-- jn: what does it mean "unpack" here? -->
# <!-- md: I've added a note with an explanation -->
# 
# ::: callout-note
# The `*` syntax in Python is known as variable-length ["*positional* arguments"](https://docs.python.org/3/glossary.html#term-argument).
# It is used to pass a `list` or `tuple` (or other iterables object) to positional arguments of a function.
# 
# For example, in the last code block, `*`, in `*src_nlcd.bounds`, is used to unpack `src_nlcd.bounds` (an iterable of length 4) to four separate arguments (`left`, `bottom`, `right`, and `top`), which `rasterio.warp.calculate_default_transform` requires in that order.
# In other words, the expression from the last example:
# ```
# rasterio.warp.calculate_default_transform(
#     src_nlcd.crs,
#     dst_crs,
#     src_nlcd.width,
#     src_nlcd.height,
#     *src_nlcd.bounds
# )
# ```
# is a shortcut of:
# ```
# rasterio.warp.calculate_default_transform(
#     src_nlcd.crs,
#     dst_crs,
#     src_nlcd.width,
#     src_nlcd.height,
#     src_nlcd.bounds[0],
#     src_nlcd.bounds[1],
#     src_nlcd.bounds[2],
#     src_nlcd.bounds[3]
# )
# ```
# "*Keyword* arguments" is a related technique; see note in @sec-raster-agg-disagg.
# :::
# 
# 
# Recall from @sec-raster-resampling that resampling using `rasterio.warp.reproject` can take place directly into a "destination" raster file connection.
# Therefore, our next step is to create the metadata file used for writing the reprojected raster to file.
# For convenience, we are taking the metadata of the source raster (`src_nlcd.meta`), making a copy (`dst_kwargs`), and then updating those specific properties that need to be changed.
# Note that the reprojection process typically creates "No Data" pixels, even when there were none in the input raster, since the raster orientation changes and the edges need to be "filled" to get back a rectangular extent.
# For example, a reprojected raster may appear as a "tilted" rectangle, inside a larger straight rectangular extent, whereas the margins around the tilted rectangle are inevitably filled with "No Data" (e.g., the white stripes surrounding the edges in @fig-raster-reproject-nlcd (b) are "No Data" pixels created as a result of reprojection). 
# <!-- jn: I am unsure if I understand the above sentence... can you try to rephrase it? -->
# <!-- md: agree, now added an example to clarify -->
# We need to specify a "No Data" value of our choice, if there is no existing definition, or keep the existing source raster "No Data" setting, such as `255` in this case.

# In[ ]:


dst_kwargs = src_nlcd.meta.copy()
dst_kwargs.update({
    'crs': dst_crs,
    'transform': dst_transform,
    'width': dst_width,
    'height': dst_height
})
dst_kwargs


# Now, we are ready to create the reprojected raster.
# Here, reprojection takes place between two file connections, meaning that the raster value arrays are not being read into memory at once.
# It is also possible to reproject into an in-memory `ndarray` object, see the [documentation](https://rasterio.readthedocs.io/en/latest/api/rasterio.warp.html#rasterio.warp.reproject).
# 
# To write the reprojected raster, we first create a destination file connection `dst_nlcd`, pointing at the output file path of our choice (`'output/nlcd_4326.tif'`), using the updated metadata object created earlier (`dst_kwargs`):

# In[ ]:


dst_nlcd = rasterio.open('output/nlcd_4326.tif', 'w', **dst_kwargs)


# Then, we use the `rasterio.warp.reproject` function to calculate and write the reprojection result into the `dst_nlcd` file connection.
# 

# In[ ]:


rasterio.warp.reproject(
    source=rasterio.band(src_nlcd, 1),
    destination=rasterio.band(dst_nlcd, 1),
    src_transform=src_nlcd.transform,
    src_crs=src_nlcd.crs,
    dst_transform=dst_transform,
    dst_crs=dst_crs,
    resampling=rasterio.enums.Resampling.nearest
)


# Note--like in the example in @sec-raster-resampling---that the `source` and `destination` accept a "band" object, created using `rasterio.band`.
# In this case, there is just one band.
# If there were more bands, we would have to repeat the procedure for each band, using `i` instead of `1` inside a [loop](https://rasterio.readthedocs.io/en/latest/topics/reproject.html#reprojecting-a-geotiff-dataset).
# Finally, we close the file connection so that the data are actually written.

# In[ ]:


dst_nlcd.close()


# Many properties of the new object differ from the previous one, including the number of columns and rows (and therefore number of cells), resolution (transformed from meters into degrees), and extent, as summarized below by comparing the `.meta` object of the source and destination rasters.

# In[ ]:


src_nlcd.meta


# In[ ]:


src_nlcd_4326 = rasterio.open('output/nlcd_4326.tif')
src_nlcd_4326.meta


# Examining the unique raster values tells us that the new raster has the same categories, plus the value `255` representing "No Data":

# In[ ]:


np.unique(src_nlcd.read(1))


# In[ ]:


np.unique(src_nlcd_4326.read(1))


# @fig-raster-reproject-nlcd illustrates the effect of reprojection, comparing `nlcd.tif` (the input) and `nlcd_4326.tif` (the reprojection result), visually.

# In[ ]:


#| label: fig-raster-reproject-nlcd
#| fig-cap: Reprojecting a categorical raster using nearest neighbor resampling
#| layout-ncol: 2
#| fig-subcap: 
#| - Original (`EPSG:26912`)
#| - Reprojected (`EPSG:4326`)
rasterio.plot.show(src_nlcd, cmap='Set3');
rasterio.plot.show(src_nlcd_4326, cmap='Set3');


# In the above example, we automatically calculated an optimal (i.e., most information preserving) destination grid using `rasterio.warp.calculate_default_transform`.
# This is appropriate when there are no specific requirements for the destination raster spatial properties.
# Namely, we are not required to obtain a specific origin and resolution, but just wish to preserve the raster values as much as possible.
# To do that, `rasterio.warp.calculate_default_transform` "tries" to keep the extent and resolution of the destination raster as similar as possible to the source.
# In other situations, however, we need to reproject a raster into a specific "template", so that it corresponds, for instance, with other rasters we use in the analysis.
# In the following code examples, we reproject the `nlcd.tif` raster, again, but this time using the `nlcd_4326.tif` reprojection result as the "template" to demonstrate this alternative workflow.
# 
# First, we create a connection to our "template" raster to read its metadata.

# In[ ]:


template = rasterio.open('output/nlcd_4326.tif')
template.meta


# Then, we create a write-mode connection to our destination raster, using this exact metadata, meaning that as the resampling result is going to have identical properties as the "template".
# <!-- jn: why 'w' and not 'rw' or 'r+'? -->
# <!-- md: almost always we need either 'r' (read existing file) or 'w' (create new file); 'r+' is an exception, when we change (e.g. the crs) an existing file. I've added a note about that following another comment above -->

# In[ ]:


dst_nlcd_2 = rasterio.open('output/nlcd_4326_2.tif', 'w', **template.meta)


# Now, we can resample and write the result with `rasterio.warp.reproject`.

# In[ ]:


rasterio.warp.reproject(
    source=rasterio.band(src_nlcd, 1),
    destination=rasterio.band(dst_nlcd_2, 1),
    src_transform=src_nlcd.transform,
    src_crs=src_nlcd.crs,
    dst_transform=dst_nlcd_2.transform,
    dst_crs=dst_nlcd_2.crs,
    resampling=rasterio.enums.Resampling.nearest
)
dst_nlcd_2.close()


# Naturally, the outputs of the last two examples---`nlcd_4326.tif` and `nlcd_4326_2.tif`---are identical, as we used the same destination grid and the same source data.
# We can check it with `np.all`.

# In[ ]:


d = rasterio.open('output/nlcd_4326.tif').read(1) == \
    rasterio.open('output/nlcd_4326_2.tif').read(1)
np.all(d)


# The difference is that in the first example we calculated the template automatically, using `rasterio.warp.calculate_default_transform`, while in the second example we used an existing raster as the "template".
# 
# Importantly, when the template raster has much more "coarse" resolution than the source raster, the `rasterio.enums.Resampling.average` (for continuous rasters) or `rasterio.enums.Resampling.mode` (for categorical rasters) resampling methods should be used, instead of `rasterio.enums.Resampling.nearest`.
# Otherwise, much of the data will be lost, as the "nearest" method can capture one pixel value only for each destination raster pixel.
# 
# Reprojecting continuous rasters (with numeric or, in this case, integer values) follows an almost identical procedure.
# This is demonstrated below with `srtm.tif` from the Shuttle Radar Topography Mission (SRTM), which represents height in meters above sea level (elevation) with the WGS84 CRS.
# 
# We will reproject this dataset into a projected CRS, but not with the nearest neighbor method.
# Instead, we will use the bilinear method which computes the output cell value based on the four nearest cells in the original raster.
# The values in the projected dataset are the distance-weighted average of the values from these four cells: the closer the input cell is to the center of the output cell, the greater its weight.
# The following code section create a text string representing WGS 84 / UTM zone 12N, and reproject the raster into this CRS, using the bilinear method.
# The code is practically the same, except for changing the source and destination file names, and replacing `rasterio.enums.Resampling.nearest` with `rasterio.enums.Resampling.bilinear`.

# In[ ]:


dst_crs = 'EPSG:32612'
dst_transform, dst_width, dst_height = rasterio.warp.calculate_default_transform(
    src_srtm.crs,
    dst_crs,
    src_srtm.width,
    src_srtm.height,
    *src_srtm.bounds
)
dst_kwargs = src_srtm.meta.copy()
dst_kwargs.update({
    'crs': dst_crs,
    'transform': dst_transform,
    'width': dst_width,
    'height': dst_height
})
dst_srtm = rasterio.open('output/srtm_32612.tif', 'w', **dst_kwargs)
rasterio.warp.reproject(
    source=rasterio.band(src_srtm, 1),
    destination=rasterio.band(dst_srtm, 1),
    src_transform=src_srtm.transform,
    src_crs=src_srtm.crs,
    dst_transform=dst_transform,
    dst_crs=dst_crs,
    resampling=rasterio.enums.Resampling.bilinear
)
dst_srtm.close()


# @fig-raster-reproject-srtm shows the input and the reprojected SRTM rasters.

# In[ ]:


#| label: fig-raster-reproject-srtm
#| fig-cap: Reprojecting a continuous raster using bilinear resampling
#| layout-ncol: 2
#| fig-subcap: 
#| - Original (`EPSG:4326`)
#| - Reprojected (`EPSG:32612`)
rasterio.plot.show(src_srtm);
rasterio.plot.show(rasterio.open('output/srtm_32612.tif'));


# ## Custom map projections {#sec-custom-map-projections}
# 
# Established CRSs captured by `AUTHORITY:CODE` identifiers such as `EPSG:4326` are well suited for many applications.
# However, it is desirable to use alternative projections or to create custom CRSs in some cases.
# @sec-which-crs-to-use mentioned reasons for using custom CRSs, and provided several possible approaches.
# Here, we show how to apply these ideas in Python.
# 
# One is to take an existing WKT definition of a CRS, modify some of its elements, and then use the new definition for reprojecting, using the reprojection methods shown above for vector layers (@sec-reprojecting-vector-geometries) and rasters (@sec-reprojecting-raster-geometries).
# For example, let's transforms the `zion.gpkg` vector layer to a custom azimuthal equidistant (AEQD) CRS.
# Using a custom AEQD CRS requires knowing the coordinates of the center point of a dataset in degrees (geographic CRS).
# In our case, this information can be extracted by calculating the centroid of the `zion` layer transformed into WGS84:

# In[ ]:


lon, lat = zion.to_crs(4326).unary_union.centroid.coords[0]
lon, lat


# Next, we can use the obtained lon/lat coordinates in `coords` to update the WKT definition of the azimuthal equidistant (AEQD) CRS seen below.
# Notice that we modified just two values below---`"Central_Meridian"` to the longitude and `"Latitude_Of_Origin"` to the latitude of our centroid.
# <!-- jn: can you explain the below syntax (if that Python-obvious, then just as a comment for me)? what's f? what's '''? -->
# <!-- md: now added a note about it -->

# In[ ]:


my_wkt = f'''PROJCS["Custom_AEQD",
 GEOGCS["GCS_WGS_1984",
  DATUM["WGS_1984",
   SPHEROID["WGS_1984",6378137.0,298.257223563]],
  PRIMEM["Greenwich",0.0],
  UNIT["Degree",0.0174532925199433]],
 PROJECTION["Azimuthal_Equidistant"],
 PARAMETER["Central_Meridian",{lon}],
 PARAMETER["Latitude_Of_Origin",{lat}],
 UNIT["Meter",1.0]]'''
print(my_wkt)


# ::: callout-note
# The above expression uses the so-called ["f-strings"](https://docs.python.org/3/tutorial/inputoutput.html#tut-f-strings) syntax, which is one of several Python techniques to embed values inside a string (as alternatives to concatenating with `+`).
# For example, given:
# ```
# x = 5
# ```
# the expression:
# ```
# f'the value of x is {x}'
# ```
# is a shortcut to:
# ```
# 'the value of x is ' + str(x)
# ```
# both returning the string `'the value of x is 5'`.
# :::
# 
# This approach's last step is to transform our original object (`zion`) to our new custom CRS (`zion_aeqd`).

# In[ ]:


zion_aeqd = zion.to_crs(my_wkt)


# Custom projections can also be made interactively, for example, using the [Projection Wizard](https://projectionwizard.org/#) web application [@savric_projection_2016].
# This website allows you to select a spatial extent of your data and a distortion property, and returns a list of possible projections.
# The list also contains WKT definitions of the projections that you can copy and use for reprojections.
# See Open Geospatial Consortium ([2019](https://r.geocompx.org/references.html#ref-opengeospatialconsortium_wellknown_2019)) for details on creating custom CRS definitions with WKT strings.
# 
# PROJ strings can also be used to create custom projections, accepting the limitations inherent to projections, especially of geometries covering large geographic areas, as mentioned in @sec-coordinate-reference-systems.
# Many projections have been developed and can be set with the `+proj=` element of PROJ strings, with dozens of projects described in detail on the [PROJ website](https://proj.org/operations/projections/index.html) alone.
# 
# When mapping the world while preserving area relationships the Mollweide projection, illustrated in @fig-mollweide, is a popular and often sensible choice [@jenny_guide_2017].
# To use this projection, we need to specify it using the proj-string element, `'+proj=moll'`, in the `.to_crs` method:

# In[ ]:


#| label: fig-mollweide
#| fig-cap: Mollweide projection of the world
world.to_crs('+proj=moll').plot(color='none', edgecolor='black');


# It is often desirable to minimize distortion for all spatial properties (area, direction, distance) when mapping the world.
# One of the most popular projections to achieve this is [Winkel tripel](http://www.winkel.org/other/Winkel%20Tripel%20Projections.htm) (`'+proj=wintri'`), illustrated in @fig-wintri.

# In[ ]:


#| label: fig-wintri
#| fig-cap: Winkel tripel projection of the world
world.to_crs('+proj=wintri').plot(color='none', edgecolor='black');


# Moreover, proj-string parameters can be modified in most CRS definitions, for example the center of the projection can be adjusted using the `+lon_0` and `+lat_0` parameters.
# The below code transforms the coordinates to the Lambert azimuthal equal-area projection centered on the longitude and latitude of New York City (@fig-azimuthal-equal-area).

# In[ ]:


#| label: fig-azimuthal-equal-area
#| fig-cap: Lambert azimuthal equal-area projection of the world centered on New York City
world.to_crs('+proj=laea +x_0=0 +y_0=0 +lon_0=-74 +lat_0=40') \
    .plot(color='none', edgecolor='black');


# More information on CRS modifications can be found in the [Using PROJ](https://proj.org/usage/index.html) documentation.
# 
# ## Exercises
# 
# ## References
