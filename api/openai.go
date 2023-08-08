package api

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"
)

const (
	OpenAIAPIURL = "https://api.openai.com/v1/chat/completions"
)

func PrepareRequestPayload(diff, template, model, explanation string) ([]byte, error) {
	systemMessage := "You are a helpful git commit assistant, you will receive a git diff and you will generate a commit message, try be meaningful and avoid generic messages."

	if template != "" {
		systemMessage += " This message should follow the following template: " + template
	}

	messages := []map[string]string{
		{
			"role":    "system",
			"content": systemMessage,
		},
	}

	if explanation != "" {
		messages = append(messages, map[string]string{
			"role":    "user",
			"content": "Here is a high level explanation of the commit: " + explanation,
		})
	}

	messages = append(messages, map[string]string{
		"role":    "user",
		"content": diff,
	})

	payload := map[string]interface{}{
		"model":    model,
		"messages": messages,
	}

	return json.Marshal(payload)
}

func CreateAPIRequest(apiKey string, payloadBytes []byte) (*http.Request, error) {
	req, err := http.NewRequest("POST", OpenAIAPIURL, bytes.NewReader(payloadBytes))
	if err != nil {
		return nil, err
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+apiKey)

	return req, nil
}

func SendAPIRequest(req *http.Request) (*http.Response, error) {
	return http.DefaultClient.Do(req)
}

func ReadResponseBody(resp *http.Response) ([]byte, error) {
	return io.ReadAll(resp.Body)
}

func ParseResponse(responseBody []byte) (string, string, error) {
	var responseData map[string]interface{}
	err := json.Unmarshal(responseBody, &responseData)
	if err != nil {
		return "", "", err
	}

	if responseData["error"] != nil {
		return "", responseData["error"].(map[string]interface{})["message"].(string), nil
	}

	choices := responseData["choices"].([]interface{})
	choice := choices[0].(map[string]interface{})
	message := choice["message"].(map[string]interface{})

	return message["content"].(string), "", nil
}
