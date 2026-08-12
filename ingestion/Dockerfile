FROM golang:1.26 AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o ingestion ./cmd

FROM alpine:latest
WORKDIR /app
COPY --from=builder /app/ingestion .
COPY migrations ./migrations
CMD ["./ingestion"]