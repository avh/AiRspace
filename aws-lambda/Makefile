# (c)2023, Arthur van Hoff, Artfahrt Inc.

TOP=${PWD}
TMP=/tmp
PKG=${TMP}/deployment_package.zip
VERSION=v1

chart-list-update:
	rm -rf ${PKG} ${TMP}/func
	mkdir -p ${TMP}/func ; cp -r src/common ${TMP}/func
	cp src/chart_list_update.py ${TMP}/func/lambda_function.py
	cd ${TMP}/func ; zip -qr ${PKG} .
	aws lambda update-function-code --function-name chart-list-update --zip-file fileb://${PKG} > /dev/null
	-aws lambda invoke --function-name chart-list-update ${TMP}/out.txt > /dev/null
	cat ${TMP}/out.txt

update-pkgs:
	rm -rf ${TMP}/airspace-pkgs ; mkdir ${TMP}/airspace-pkgs ; cp requirements.txt ${TMP}/airspace-pkgs
	cd ${TMP}/airspace-pkgs ; docker run -v .:/var/task --platform "linux/amd64" "public.ecr.aws/sam/build-python3.8" /bin/sh -c "pip install -r requirements.txt -t python/lib/python3.8/site-packages/; exit"
	cd ${TMP}/airspace-pkgs ; zip -qr9 $(TMP)/airspace-pkgs.zip python
	aws lambda publish-layer-version --layer-name airspace-pkgs --zip-file fileb://${TMP}/airspace-pkgs.zip --compatible-runtimes "python3.8"

deploy-www:
	aws s3 sync www s3://airspace.artfahrt.com/www/${VERSION}/