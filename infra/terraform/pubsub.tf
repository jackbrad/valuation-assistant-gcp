resource "google_pubsub_topic" "flags" {
  name = "flags"
}

resource "google_pubsub_topic" "corrections" {
  name = "corrections"
}
