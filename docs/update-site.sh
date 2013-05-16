#!/bin/bash
#Script to update gh-pages

set -e

TMP_REPO=`mktemp -d -t conpot-site`
TMP_HTML=`mktemp -d -t conpot-site`

make html
cp -R build/html/* $TMP_HTML

git clone git@github.com:glastopf/conpot.git $TMP_REPO
cd $TMP_REPO
git checkout gh-pages
git symbolic-ref HEAD refs/heads/gh-pages
rm .git/index
git clean -fdx
cp -R $TMP_HTML/* $TMP_REPO
touch $TMP_REPO/.nojekyll
git add .
git commit -a -m "Site update"
git push origin gh-pages
rm -rf $TMP_REPO
rm -rf $TMP_HTML
