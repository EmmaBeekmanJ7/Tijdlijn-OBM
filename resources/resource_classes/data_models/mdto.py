"""MDTO data models"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .base import BaseModel


@dataclass
class Informatietype(BaseModel):
    label: Optional[str] = None
    uri: Optional[str] = None


@dataclass
class ParlementairType(BaseModel):
    label: Optional[str] = None
    uri: Optional[str] = None


@dataclass
class Taal(BaseModel):
    label: Optional[str] = None
    uri: Optional[str] = None


@dataclass
class OrganisatieType(BaseModel):
    label: Optional[str] = None
    uri: Optional[str] = None


@dataclass
class Organisatie(BaseModel):
    naam: Optional[str] = None
    organisatieType: OrganisatieType = field(default_factory=OrganisatieType)
    uri: Optional[str] = None


@dataclass
class Relatie(BaseModel):
    targetIdentificatie: Optional[str] = None


@dataclass
class Bestand(BaseModel):
    weergaveURL: Optional[str] = None
    documentURL: Optional[str] = None
    bestandsformaat: Optional[Dict[str, str]] = None


@dataclass
class TechnischeContext(BaseModel):
    configuratieSchema: Optional[str] = None
    doctype: Optional[str] = None


@dataclass
class Informatieobject(BaseModel):
    identificatie: Optional[str] = None
    titel: Optional[str] = None
    status: Optional[str] = None
    informatietype: Informatietype = field(default_factory=Informatietype)
    parlementairType: ParlementairType = field(default_factory=ParlementairType)
    dossierNummer: Optional[str] = None
    ondernummer: Optional[str] = None
    vergaderjaar: Optional[str] = None
    taal: Taal = field(default_factory=Taal)
    beschikbaarVanaf: Optional[str] = None
    organisatie: Organisatie = field(default_factory=Organisatie)
    relaties: List[Relatie] = field(default_factory=list)
    bestanden: List[Bestand] = field(default_factory=list)
    technischeContext: TechnischeContext = field(default_factory=TechnischeContext)


@dataclass
class MDTO(BaseModel):
    informatieobject: Informatieobject = field(default_factory=Informatieobject)
