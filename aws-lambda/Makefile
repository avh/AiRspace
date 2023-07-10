# (c)2023, Arthur van Hoff, Artfahrt Inc.

TOP=${PWD}
TMP=/tmp
PKG=${TMP}/deployment_package.zip
VERSION=v1

chart-list-update: src/chart-list-update.py
	-aws lambda invoke --function-name chart-list-update ${TMP}/out.txt --output text
	cat ${TMP}/out.txt

deploy-www:
	aws s3 sync www s3://airspace.artfahrt.com/www/${VERSION}/

src/%.py: .FORCE
	rm -rf ${TMP}/$*.zip ${TMP}/$*
	mkdir -p ${TMP}/$* ; cp -r src/common ${TMP}/$*
	cp src/$*.py ${TMP}/$*/lambda_function.py
	cd ${TMP}/$* ; zip -qr ${TMP}/$*.zip .
	aws lambda update-function-code --function-name $* --zip-file fileb://${TMP}/$*.zip --output text

update-pkgs:
	rm -rf ${TMP}/airspace-pkgs ; mkdir ${TMP}/airspace-pkgs ; cp requirements.txt ${TMP}/airspace-pkgs
	cd ${TMP}/airspace-pkgs ; docker run -v .:/var/task --platform "linux/amd64" "public.ecr.aws/sam/build-python3.8" /bin/sh -c "pip install -r requirements.txt -t python/lib/python3.8/site-packages/; exit"
	cd ${TMP}/airspace-pkgs ; zip -qr9 $(TMP)/airspace-pkgs.zip python
	aws lambda publish-layer-version --layer-name airspace-pkgs --zip-file fileb://${TMP}/airspace-pkgs.zip --compatible-runtimes "python3.8"

.FORCE: