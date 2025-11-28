from fastapi import Request
from fastapi import Depends, FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from typing import List
from sqlalchemy.orm import Session
from config.database import SessionLocal
from crud import *
from models.Models import Prestamo, Usuario, Libro
from arboles import ArbolBinarioBusqueda
from networkx.readwrite import json_graph
import networkx as nx


# Crear la app FastAPI
app = FastAPI()




# Configurar Jinja2 para servir plantillas
templates = Jinja2Templates(directory="templates")

# Montar la carpeta static para archivos CSS e imágenes
app.mount("/static", StaticFiles(directory="static"), name="static")

# Estructuras de datos
libros = []  # Lista para almacenar libros
usuarios = []  # Lista para almacenar usuarios
prestamos = []  # Lista para almacenar préstamos


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def insert_libro(
    titulo: str, autor: str, isbn: str, editorial: int, anio: int, db: Session = Depends(get_db)
):
    return crear_libro(db, titulo, autor, isbn, editorial, anio)


@app.on_event("startup")
def inicializar_arbol():
    app.state.libros_arbol = ArbolBinarioBusqueda()
    db = SessionLocal()
    libros = db.query(Libro).all()
    for libro in libros:
        app.state.libros_arbol.insertar(libro.titulo, libro)
    db.close()


def reconstruir_arbol(app: FastAPI):
    arbol = ArbolBinarioBusqueda()
    db = SessionLocal()
    libros = db.query(Libro).all()
    for libro in libros:
        arbol.insertar(libro.titulo, libro)
    db.close()

    app.state.libros_arbol = arbol

"""
Cuando inicias la aplicación:

- Crea un árbol binario de búsqueda donde los libros se organizan automáticamente por sus títulos.

- Permite buscar libros de manera eficiente utilizando el título como criterio principal.

- Prepara la aplicación para que las consultas relacionadas con búsquedas sean rápidas y escalables, ya que el árbol optimiza la operación de búsqueda en comparación con recorrer una lista completa.
"""


# Ruta para la página de inicio
@app.get("/", response_class=HTMLResponse)
def leer_inicio(request: Request):
    return templates.TemplateResponse("inicio.html", {"request": request})

# Rutas para la gestión de libros
@app.get("/libros", response_class=HTMLResponse)
def obtener_libros(request: Request, db: Session = Depends(get_db), mensaje: str = None):
    libros = db.query(Libro).all()
    return templates.TemplateResponse("libros.html", {"request": request, "libros": libros, "mensaje": mensaje})

@app.post("/libros", response_class=HTMLResponse)
def agregar_libro(
    request: Request,
    titulo: str = Form(...), 
    autor: str = Form(...), 
    isbn: str = Form(...), 
    editorial: str = Form(...), 
    anio: int = Form(...),
    db: Session = Depends(get_db)
):
    # Validar si ya existe un libro con el mismo título
    libro_existente = db.query(Libro).filter(Libro.titulo == titulo).first()
    if libro_existente:
        return templates.TemplateResponse(
            "libros.html", 
            {
                "request": request, 
                "libros": db.query(Libro).all(),
                "mensaje": f"El libro con el título '{titulo}' ya existe en la base de datos."
            }
        )

    # Crear el nuevo libro si no existe
    nuevo_libro = crear_libro(db, titulo, autor, isbn, editorial, anio)
    reconstruir_arbol(request.app)

    #return templates.TemplateResponse("libros.html", {"request": request})
    return templates.TemplateResponse(
        "libros.html", 
        {
            "request": request, 
            "libros": db.query(Libro).all(),
            "mensaje": "Libro agregado correctamente."
        }
    )


#edita cualquier campo del libro
@app.post("/editar_libro")
def editar_libro(
    titulo: str = Form(...),
    autor: str = Form(...),
    isbn: str = Form(...),
    editorial: str = Form(...),
    anio: int = Form(...),
    db: Session = Depends(get_db)
):
    libro = db.query(Libro).filter(Libro.titulo == titulo).first()
    if libro:
        libro.autor = autor
        libro.isbn = isbn
        libro.editorial = editorial
        libro.anio = anio
        db.commit()
    return RedirectResponse(url="/libros", status_code=303)

#elimina el libro seleccionado
@app.post("/eliminar_libro")
def eliminar_libro(titulo: str = Form(...), db: Session = Depends(get_db)):
    libro = db.query(Libro).filter(Libro.titulo == titulo).first()
    if libro:
        db.delete(libro)
        db.commit()
    return RedirectResponse(url="/libros", status_code=303)

@app.post("/eliminar_libro_busqueda")
def eliminar_libro(
    titulo: str = Form(...),
    request: Request = None,  
    db: Session = Depends(get_db)
):
    libro = db.query(Libro).filter(Libro.titulo == titulo).first()
    if libro:
        db.delete(libro)
        db.commit()
        arbol = request.app.state.libros_arbol
        arbol.eliminar(titulo)  

    return templates.TemplateResponse("busquedas.html", {"request": request, "libros": libros, "mensaje": "¡ Libro eliminado correctamente !"})
    




# Rutas para la gestión de usuarios
@app.get("/usuarios", response_class=HTMLResponse)
def leer_usuarios(request: Request,db: Session = Depends(get_db)):
    return templates.TemplateResponse("usuarios.html", {"request": request, "usuarios": db.query(Usuario).all()})

@app.post("/usuarios", response_class=HTMLResponse)
def agregar_usuario(
    request: Request,
    nombre: str = Form(...),
    identificacion: str = Form(...),
    db: Session = Depends(get_db)
):
    # Verificar si el usuario ya existe por el nombre
    usuario_existente = db.query(Usuario).filter(Usuario.nombre == nombre).first()
    if usuario_existente:
        return templates.TemplateResponse(
            "usuarios.html", 
            {
                "request": request, 
                "usuarios": db.query(Usuario).all(),
                "mensaje": f"El usuario con el nombre '{nombre}' ya existe."
            }
        )
    
    # Crear el nuevo usuario
    nuevo_usuario = Usuario(nombre=nombre, identificacion=identificacion)
    db.add(nuevo_usuario)
    db.commit()
    return templates.TemplateResponse(
        "usuarios.html",
        {
            "request": request,
            "usuarios": db.query(Usuario).all(),
            "mensaje": "Usuario registrado correctamente."
        }
    )

@app.post("/editar_usuario", response_class=HTMLResponse)
def editar_usuario(
    request: Request,
    nombre_actual: str = Form(...),
    nuevo_nombre: str = Form(...),
    nueva_identificacion: str = Form(...),
    db: Session = Depends(get_db)
):
    # Buscar el usuario a editar por el nombre actual
    usuario = db.query(Usuario).filter(Usuario.nombre == nombre_actual).first()
    if not usuario:
        return templates.TemplateResponse(
            "usuarios.html", 
            {
                "request": request, 
                "usuarios": db.query(Usuario).all(),
                "mensaje": f"El usuario con el nombre '{nombre_actual}' no existe."
            }
        )
    
    # Verificar si el nuevo nombre ya existe en otro usuario
    usuario_con_nuevo_nombre = db.query(Usuario).filter(Usuario.nombre == nuevo_nombre).first()
    if usuario_con_nuevo_nombre and usuario_con_nuevo_nombre.nombre != nombre_actual:
        return templates.TemplateResponse(
            "usuarios.html", 
            {
                "request": request, 
                "usuarios": db.query(Usuario).all(),
                "mensaje": f"El nombre '{nuevo_nombre}' ya está en uso por otro usuario."
            }
        )
    
    # Actualizar los datos del usuario
    usuario.nombre = nuevo_nombre
    usuario.identificacion = nueva_identificacion
    db.commit()

    return templates.TemplateResponse(
        "usuarios.html",
        {
            "request": request,
            "usuarios": db.query(Usuario).all(),
            "mensaje": f"Datos del usuario '{nuevo_nombre}' actualizados correctamente."
        }
    )


@app.post("/eliminar_usuario", response_class=HTMLResponse)
def eliminar_usuario(
    request: Request,
    nombre: str = Form(...),
    db: Session = Depends(get_db)
):
    usuario = db.query(Usuario).filter(Usuario.nombre == nombre).first()
    if not usuario:
        return templates.TemplateResponse(
            "usuarios.html", 
            {
                "request": request, 
                "usuarios": db.query(Usuario).all(),
                "mensaje": f"El usuario con el nombre '{nombre}' no existe."
            }
        )
    
    # Eliminar el usuario
    db.delete(usuario)
    db.commit()
    return templates.TemplateResponse(
        "usuarios.html",
        {
            "request": request,
            "usuarios": db.query(Usuario).all(),
            "mensaje": f"Usuario '{nombre}' eliminado correctamente."
        }
    )



@app.get("/prestamos", response_class=HTMLResponse)
def leer_usuarios(request: Request,db: Session = Depends(get_db)):
    return templates.TemplateResponse("prestamos.html", {"request": request, "prestamos": db.query(Prestamo).all()})

# Rutas para la gestión de préstamos
@app.post("/prestamos", response_class=HTMLResponse)
def agregar_prestamo(
    request: Request,
    usuario: str = Form(...),
    libro: str = Form(...),
    db: Session = Depends(get_db)
):
    # Verificar existencia del usuario y del libro
    usuario_obj = db.query(Usuario).filter(Usuario.nombre == usuario).first()
    libro_obj = db.query(Libro).filter(Libro.isbn == libro).first()

    if not usuario_obj:
        mensaje = f"El usuario '{usuario}' no existe en la base de datos."
    elif not libro_obj:
        mensaje = f"El libro con ISBN '{libro}' no existe en la base de datos."
    else:
        # Crear el préstamo
        nuevo_prestamo = Prestamo(usuario_id=usuario_obj.id, libro_id=libro_obj.id)
        db.add(nuevo_prestamo)
        db.commit()
        mensaje = "Préstamo registrado correctamente."

    return templates.TemplateResponse(
        "prestamos.html",
        {
            "request": request,
            "prestamos": db.query(Prestamo).all(),
            "mensaje": mensaje
        }
    )



@app.post("/editar_prestamo", response_class=HTMLResponse)
def editar_prestamo(
    request: Request,
    prestamo_id: int = Form(...),
    nuevo_usuario: str = Form(...),
    nuevo_libro: str = Form(...),
    db: Session = Depends(get_db)
):
    prestamo = db.query(Prestamo).filter(Prestamo.id == prestamo_id).first()
    usuario_obj = db.query(Usuario).filter(Usuario.nombre == nuevo_usuario).first()
    libro_obj = db.query(Libro).filter(Libro.isbn == nuevo_libro).first()

    if not prestamo:
        mensaje = f"El préstamo con ID '{prestamo_id}' no existe."
    elif not usuario_obj:
        mensaje = f"El usuario '{nuevo_usuario}' no existe en la base de datos."
    elif not libro_obj:
        mensaje = f"El libro con ISBN '{nuevo_libro}' no existe en la base de datos."
    else:
        prestamo.usuario_id = usuario_obj.id
        prestamo.libro_id = libro_obj.id
        db.commit()
        mensaje = "Préstamo actualizado correctamente."

    return templates.TemplateResponse(
        "prestamos.html",
        {
            "request": request,
            "prestamos": db.query(Prestamo).all(),
            "mensaje": mensaje
        }
    )
@app.get("/prestamos", response_class=HTMLResponse)
def leer_prestamos(request: Request):
    
    return templates.TemplateResponse("prestamos.html", {"request": request, "prestamos": prestamos})



@app.post("/prestamos")
def agregar_prestamos(
    libro: str = Form(...), 
    usuario: str = Form(...)
):
    nuevo_prestamo = {"libro": libro, "usuario": usuario}
    prestamos.append(nuevo_prestamo)
    return templates.TemplateResponse("prestamos.html", {"request": {}, "prestamos": prestamos})



@app.post("/eliminar_prestamo", response_class=HTMLResponse)
def eliminar_prestamo(
    request: Request,
    prestamo_id: int = Form(...),
    db: Session = Depends(get_db)
):
    prestamo = db.query(Prestamo).filter(Prestamo.id == prestamo_id).first()

    if not prestamo:
        mensaje = f"El préstamo con ID '{prestamo_id}' no existe."
    else:
        db.delete(prestamo)
        db.commit()

        mensaje = "Préstamo eliminado correctamente."

    return templates.TemplateResponse(
        "prestamos.html",
        {
            "request": request,
            "prestamos": db.query(Prestamo).all(),
            "mensaje": mensaje
        }
    )



""""
Guardar -- insert
actualizar -- update
leer en pantalla -- select
eliminar -- delete

"""

#Segunda Fase, ARBOLES

#Ruta para busquedas
@app.get("/busquedas/libros", response_class=HTMLResponse)
def buscar_libro(request: Request, titulo: str = None):
    mensaje = None
    libro = None

    if titulo:
        arbol = request.app.state.libros_arbol  
        libro = arbol.buscar(titulo)
        print(libro)
        if libro:
            mensaje = "¡Libro encontrado!"
        else:
            mensaje = "Libro no encontrado"

    return templates.TemplateResponse(
        "busquedas.html",
        {"request": request, "libro": libro, "mensaje": mensaje}
    )



#devoluciones
@app.get("/devoluciones", response_class=HTMLResponse)
def devoluciones_inicio(request: Request, mensaje: str = None):
    response = templates.TemplateResponse("devoluciones.html", {
        "request": request,
        "mensaje": mensaje
    })
    return response

@app.post("/devoluciones")
def devolver_libro(
    isbn: str = Form(...),
    usuario_id: str = Form(...),      
    request: Request = None,
    db: Session = Depends(get_db)
):
    libro = db.query(Libro).filter(Libro.isbn == isbn).first()
    persona = db.query(Usuario).filter(Usuario.identificacion == usuario_id).first()

    if not libro:
            return templates.TemplateResponse(
        "devoluciones.html",
        {"request": request, "mensaje": f"Libro {isbn} no encontrado"}
    )

    try:
        prestamo = db.query(Prestamo).filter(
            Prestamo.usuario_id == persona.id,
            Prestamo.libro_id == libro.id
        ).first()
    except:
        return templates.TemplateResponse(
        "devoluciones.html",
        {"request": request, "mensaje": "Identificación no encontrada en el sistema"}
    )

    if not prestamo:
        return templates.TemplateResponse(
        "devoluciones.html",
        {"request": request, "mensaje": "No se encontró un préstamo activo de este libro para el usuario."}
    )

    db.delete(prestamo)
    db.commit()
    
    #rbol = request.app.state.libros_arbol
    #arbol.insertar(libro.titulo, libro) 
    return templates.TemplateResponse(
        "devoluciones.html",
        {"request": request, "libro": libro, "mensaje": f"Libro ha sido devuelto con exito"}
    )
"""
@app.get("/grafo_usuario")
def construir_grafo_usuario(db: Session):
    G = nx.DiGraph()
    usuarios = db.query(Usuario).all()
    for usuario in usuarios:
        G.add_node(f"U{usuario.id}", label=usuario.nombre, tipo="usuario")
    data = json_graph.node_link_data(G)
    print("hola")
    return data 
"""

def construir_grafo(db: Session):
    G = nx.DiGraph()
    # Nodos de usuarios
    usuarios = db.query(Usuario).all()
    for usuario in usuarios:
        G.add_node(f"U{usuario.id}", label=usuario.nombre, tipo="usuario")
    
    # Nodos de libros
    libros = db.query(Libro).all()
    for libro in libros:
        G.add_node(f"L{libro.id}", label=libro.titulo, tipo="libro")
    
    # Aristas: prestamos
    prestamos = db.query(Prestamo).all()
    for prestamo in prestamos:
        G.add_edge(f"U{prestamo.usuario_id}", f"L{prestamo.libro_id}")
    
    return G



@app.get("/grafo")
def obtener_grafo(db: Session = Depends(get_db)):
    G = construir_grafo(db)
    data = json_graph.node_link_data(G) 
    return data

@app.get("/grafo_usuario/{nombre}")
def grafo_usuario(nombre: str, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.nombre == nombre).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    G = nx.DiGraph()
    G.add_node(f"U{usuario.id}", label=usuario.nombre, tipo="usuario")

    prestamos = db.query(Prestamo).filter(Prestamo.usuario_id == usuario.id).all()
    libro_ids = [p.libro_id for p in prestamos]

    libros = db.query(Libro).filter(Libro.id.in_(libro_ids)).all()
    for libro in libros:
        G.add_node(f"L{libro.id}", label=libro.titulo, tipo="libro")
        G.add_edge(f"U{usuario.id}", f"L{libro.id}")

    return json_graph.node_link_data(G)
