from geoalchemy2 import Geometry
from sqlalchemy import BigInteger, Column, Text

from database.mapserver_database import MapServerBase


class PlanetOsmPoint(MapServerBase):
    __tablename__ = "planet_osm_point"
    __table_args__ = {"schema": "public"}

    osm_id = Column(BigInteger, primary_key=True)
    name = Column(Text)
    amenity = Column(Text)
    aeroway = Column(Text)
    railway = Column(Text)
    shop = Column(Text)
    tourism = Column(Text)
    place = Column(Text)
    building = Column(Text)
    leisure = Column(Text)
    way = Column(Geometry(geometry_type="POINT", srid=3857), nullable=False)


class PlanetOsmPolygon(MapServerBase):
    __tablename__ = "planet_osm_polygon"
    __table_args__ = {"schema": "public"}

    osm_id = Column(BigInteger, primary_key=True)
    name = Column(Text)
    amenity = Column(Text)
    aeroway = Column(Text)
    railway = Column(Text)
    shop = Column(Text)
    tourism = Column(Text)
    place = Column(Text)
    building = Column(Text)
    leisure = Column(Text)
    way = Column(Geometry(geometry_type="GEOMETRY", srid=3857), nullable=False)
