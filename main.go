package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"strings"

	"github.com/urfave/cli/v2"
)

const (
	OpenAIAPIURL = "https://api.openai.com/v1/chat/completions"
)

var (
	OpenAI_API_KEY  = os.Getenv("OPENAI_API_KEY")
	TEMPLATE_COMMIT = os.Getenv("TEMPLATE_COMMIT")
)

func getStagedDiff() (string, error) {
	cmd := exec.Command("git", "diff", "--staged")
	var out bytes.Buffer
	cmd.Stdout = &out
	err := cmd.Run()
	if err != nil {
		return "", err
	}

	diff := out.String()
	if strings.TrimSpace(diff) == "" {
		return "", nil
	}

	return diff, nil
}

func generateCommitMessage(apiKey string, diff string, template string) (string, error) {
	systemMessage := "You are a helpful git commit assistant, you will receive a git diff and you will generate a commit message."

	if template != "" {
		systemMessage += " This message should follow the following template: " + template
	}

	payload := map[string]interface{}{
		"model": "gpt-4",
		"messages": []map[string]string{
			{
				"role":    "system",
				"content": systemMessage,
			},
			{
				"role":    "user",
				"content": diff,
			},
		},
	}

	payloadBytes, err := json.Marshal(payload)
	if err != nil {
		return "", err
	}

	req, err := http.NewRequest("POST", OpenAIAPIURL, bytes.NewReader(payloadBytes))
	if err != nil {
		return "", err
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+apiKey)

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("Error: Failed to generate commit message using OpenAI API")
	}

	responseBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", err
	}

	var responseData map[string]interface{}
	err = json.Unmarshal(responseBody, &responseData)
	if err != nil {
		return "", err
	}

	choices := responseData["choices"].([]interface{})
	choice := choices[0].(map[string]interface{})
	message := choice["message"].(map[string]interface{})

	return message["content"].(string), nil
}

func createCommit(commitMessage string) error {
	cmd := exec.Command("git", "commit", "-m", commitMessage)
	err := cmd.Run()
	if err != nil {
		return err
	}

	return nil
}

func main() {
	app := &cli.App{
		Name:  "git-commit-helper",
		Usage: "Generate git commit messages using GPT-4",
		Flags: []cli.Flag{
			&cli.BoolFlag{
				Name:    "commit",
				Aliases: []string{"m"},
				Usage:   "Commit the changes with the generated message",
			},
			&cli.StringFlag{
				Name:    "template",
				Aliases: []string{"t"},
				Value:   TEMPLATE_COMMIT,
				Usage:   "Specify a commit message template",
			},
		},
		Action: func(c *cli.Context) error {
			if OpenAI_API_KEY == "" {
				fmt.Println("Error: OPENAI_API_KEY environment variable not set")
				os.Exit(1)
			}

			diff, err := getStagedDiff()
			if err != nil {
				fmt.Println("Error: Failed to get staged diff")
				os.Exit(1)
			}

			if diff == "" {
				fmt.Println("Warning: No staged changes found. Exiting.")
				os.Exit(0)
			}

			template := c.String("template")
			commitMessage, err := generateCommitMessage(OpenAI_API_KEY, diff, template)
			if err != nil {
				fmt.Println(err)
				os.Exit(1)
			}

			if c.Bool("commit") {
				err := createCommit(commitMessage)
				if err != nil {
					fmt.Println("Error: Failed to create commit")
					os.Exit(1)
				}
			} else {
				fmt.Printf("Generated commit message: \n\n %s\n", commitMessage)
			}

			return nil
		},
	}

	err := app.Run(os.Args)
	if err != nil {
		fmt.Println(err)
		os.Exit(1)
	}
}
