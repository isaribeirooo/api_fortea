from typing import Optional

import pymysql
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="API ForTEA")

CAMPOS = [
    "nome", "especialidade", "descricao", "telefone", "whatsapp",
    "endereco", "site", "convenios", "atendimento", "valor_consulta",
    "foto", "ativo",
]


def get_conn():
    return pymysql.connect(
        host="localhost",
        user="root",
        password="",
        database="fortea",
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


class ProfissionalIn(BaseModel):
    nome: str
    especialidade: Optional[str] = None
    descricao: Optional[str] = None
    telefone: Optional[str] = None
    whatsapp: Optional[str] = None
    endereco: Optional[str] = None
    site: Optional[str] = None
    convenios: Optional[str] = None
    atendimento: Optional[str] = None
    valor_consulta: Optional[str] = None
    foto: Optional[str] = None
    ativo: int = 1


@app.get("/")
def raiz():
    return {"mensagem": "API ForTEA funcionando. Veja /docs"}


@app.get("/profissionais")
def listar():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM profissionais ORDER BY nome")
            return cur.fetchall()
    finally:
        conn.close()


@app.get("/profissionais/{id}")
def visualizar(id: int):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM profissionais WHERE id = %s", (id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(404, "Profissional não encontrado")
            return row
    finally:
        conn.close()


@app.post("/profissionais", status_code=201)
def cadastrar(p: ProfissionalIn):
    dados = p.model_dump()
    colunas = ", ".join(CAMPOS)
    marcadores = ", ".join(["%s"] * len(CAMPOS))
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO profissionais ({colunas}) VALUES ({marcadores})",
                [dados[c] for c in CAMPOS],
            )
            conn.commit()
            return {"id": cur.lastrowid, **dados}
    finally:
        conn.close()


@app.put("/profissionais/{id}")
def editar(id: int, p: ProfissionalIn):
    dados = p.model_dump()
    sets = ", ".join(f"{c} = %s" for c in CAMPOS)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE profissionais SET {sets} WHERE id = %s",
                [dados[c] for c in CAMPOS] + [id],
            )
            conn.commit()
            return {"id": id, **dados}
    finally:
        conn.close()


@app.delete("/profissionais/{id}")
def excluir(id: int):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM profissionais WHERE id = %s", (id,))
            conn.commit()
            if cur.rowcount == 0:
                raise HTTPException(404, "Profissional não encontrado")
            return {"mensagem": "Excluído com sucesso"}
    finally:
        conn.close()