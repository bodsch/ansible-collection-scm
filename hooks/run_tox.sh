#!/usr/bin/env bash

. hooks/molecule.rc

# set -x
# set -e

TOX_TEST="${1}"

if [[ ! -z "${COLLECTION_ROLE// }" ]]
then
  if [ -d "roles/${COLLECTION_ROLE}" ]
  then
    echo "- ${COLLECTION_ROLE} - ${COLLECTION_SCENARIO}"
    echo ""

    pushd "roles/${COLLECTION_ROLE}" > /dev/null

    if [ -e collections.yml ]
    then
      ansible_collection
    fi

    tox "${TOX_OPTS}" -- molecule ${TOX_TEST} --scenario-name ${COLLECTION_SCENARIO}

    echo ""
    popd > /dev/null
  else
    echo "collection role ${COLLECTION_ROLE} not found"
  fi
else
  for role in $(find roles -maxdepth 1 -mindepth 1 -type d -printf "%f\n")
  do
    echo "- ${role} - ${COLLECTION_SCENARIO}"
    echo ""

    pushd roles/${role} > /dev/null

    if [ -e collections.yml ]
    then
      ansible_collection
    fi

    if [ "${TOX_TEST}" = "lint" ]
    then
      set +e
      ansible-lint .
      yamllint .
      flake8 .
      echo "done."
    else
      if [ -f "./tox.ini" ]
      then
        for test in $(find molecule -maxdepth 1 -mindepth 1 -type d -printf "%f\n")
        do
          export TOX_SCENARIO=${test}

          tox "${TOX_OPTS}" -- molecule ${TOX_TEST} ${TOX_ARGS}
        done
      fi
    fi

    echo ""
    popd > /dev/null
  done
fi
