# Copyright (c) 2026, Renaud Allard <renaud@allard.it>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

"""Barista recipe slot information.

CHAR_RECIPE_INFO says how many recipes the machine can hold and how big each
may be, verified against RecipeCommand.java in the APK. Recipe editing itself
is not implemented.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RecipeInfo:
    """Machine recipe slot information from CHAR_RECIPE_INFO."""

    max_recipes: int
    nb_default_recipes: int
    max_recipe_size: int
    max_recipe_steps: int
    max_recipe_phases: int
    max_recipe_name_length: int
    max_step_name_length: int


def parse_recipe_info(data: bytes) -> RecipeInfo:
    """Parse 8-byte CHAR_RECIPE_INFO."""
    if len(data) < 8:
        raise ValueError(f"Recipe info requires >= 8 bytes, got {len(data)}")
    return RecipeInfo(
        max_recipes=data[0],
        nb_default_recipes=data[1],
        max_recipe_size=int.from_bytes(data[2:4], "big"),
        max_recipe_steps=data[4],
        max_recipe_phases=data[5],
        max_recipe_name_length=data[6],
        max_step_name_length=data[7],
    )
