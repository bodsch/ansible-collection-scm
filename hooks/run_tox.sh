#!/usr/bin/env bash

. hooks/molecule.rc

set -e

TOX_TEST="${1}"

if [[ ! -z "${COLLECTION_ROLE// }" ]]
then
  if [ -d "roles/${COLLECTION_ROLE}" ]
  then
    echo "- ${COLLECTION_ROLE} - ${COLLECTION_SCENARIO}"
    echo ""

    pushd "roles/${COLLECTION_ROLE}"

    tox "${TOX_OPTS}" -- molecule ${TOX_TEST} --scenario-name ${COLLECTION_SCENARIO}

    echo ""
    popd
  else
    echo "collection role ${COLLECTION_ROLE} not found"
  fi
else
  if [ ! -d roles ]
  then
    exit 0
  fi

  for role in $(find roles -maxdepth 1 -mindepth 1 -type d -printf "%f\n")
  do
    echo "- ${role} - ${COLLECTION_SCENARIO}"
    echo ""

    pushd roles/${role}

    if [ -f "./tox.ini" ]
    then
      for test in $(find molecule -maxdepth 1 -mindepth 1 -type d -printf "%f\n")
      do
        export TOX_SCENARIO=${test}

        tox "${TOX_OPTS}" -- molecule ${TOX_TEST} ${TOX_ARGS}
      done
    fi

    echo ""
    popd
  done
fi
