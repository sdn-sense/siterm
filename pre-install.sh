#!/bin/bash
# Copyright 2024 ESnet
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#       http://www.apache.org/licenses/LICENSE-2.0
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
# Title             : siterm
# Author            : Justas Balcas
# Email             : jbalcas (at) es.net
# @Copyright        : Copyright (C) 2024 ESnet
# Date            : 2024/06/26
# =============================================================================

if [ "$1" == "dev" ]; then
  # Get current version from release/current_tag
  CURRENT_VERSION=$(cat release/current_tag)
  echo "Running version-update.sh to update version to dev"
  ./release/version-update.sh $CURRENT_VERSION-dev
fi
