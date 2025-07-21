#!/usr/bin/bash 


poetry env use python3.11
poetry install --with dev
poetry lock
