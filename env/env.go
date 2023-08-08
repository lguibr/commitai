package env

import "os"

var (
	OpenAI_API_KEY  = os.Getenv("OPENAI_API_KEY")
	TEMPLATE_COMMIT = os.Getenv("TEMPLATE_COMMIT")
)
