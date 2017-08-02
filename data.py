from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
 
from database import Restaurant, Base, MenuItem, User
 
engine = create_engine('postgresql://catalog:password@localhost/catalog')

Base.metadata.bind = engine
 
DBSession = sessionmaker(bind=engine)
session = DBSession()

restaurant1 = Restaurant(name = "Zaza Burger")
restaurant2 = Restaurant(name = "Nana pizza")
restaurant3 = Restaurant(name = "seka pasta")
session.add(restaurant1)
session.add(restaurant2)
session.add(restaurant3)
session.commit()