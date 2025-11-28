from sqlalchemy.orm import Session

from models.Models import Libro


def crear_libro(db: Session, titulo: str, autor: str, isbn: str, editorial: str, anio: int):
    nuevo_libro = Libro(titulo=titulo, autor=autor, isbn=isbn, editorial=editorial, anio=anio)
    db.add(nuevo_libro)
    db.commit()
    db.refresh(nuevo_libro)
    return nuevo_libro

def obtener_libros(db: Session):
    return db.query(Libro).all()