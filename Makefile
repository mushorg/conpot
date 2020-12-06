.PHONY: docker
build-docker:
	docker build -t conpot:latest .

run-docker: build-docker
	docker run -it -p 80:8800 -p 102:10201 -p 502:5020 -p 161:16100/udp -p 47808:47808/udp -p 623:6230/udp -p 21:2121 -p 69:6969/udp -p 44818:44818 --network=bridge conpot:latest
