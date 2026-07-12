.PHONY: build test lint bench clean

BINARY := mslearn
PKG    := ./...

build:
	go build -o $(BINARY) ./cmd/mslearn

test:
	go test -race -count=1 $(PKG)

lint:
	go vet $(PKG)

bench:
	go test -bench=. -benchmem -run='^$$' $(PKG)

clean:
	rm -f $(BINARY)
