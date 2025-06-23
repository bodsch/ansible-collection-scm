#!/usr/bin/env bash

. hooks/molecule.rc

# set -x
set -e

current_dir=$(pwd)

TOX_TEST="${1}"

echo ""
echo "global"
${current_dir}/hooks/manage_collections.py

if [[ ! -z "${COLLECTION_ROLE// }" ]]
then
  if [ -d "roles/${COLLECTION_ROLE}" ]
  then
    echo "- ${COLLECTION_ROLE} - ${COLLECTION_SCENARIO}"
    echo ""

    for i in requirements.txt test-requirements.txt tox.ini
    do
      if [ -e "${i}" ]
      then
        cp "${i}" "roles/${COLLECTION_ROLE}/"
      fi
    done

    pushd "roles/${COLLECTION_ROLE}" > /dev/null

    if [ -e collections.yml ]
    then
      ${current_dir}/hooks/manage_collections.py --scenario ${COLLECTION_SCENARIO}
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

    for i in requirements.txt test-requirements.txt tox.ini
    do
      if [ -e "${i}" ]
      then
        cp "${i}" "roles/${COLLECTION_ROLE}/"
      fi
    done

    pushd roles/${role} > /dev/null

    if [ -e collections.yml ]
    then
      ${current_dir}/hooks/manage_collections.py --scenario ${COLLECTION_SCENARIO}
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
