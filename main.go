package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
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

func getRepositoryName() (string, error) {
	cmd := exec.Command("git", "rev-parse", "--show-toplevel")
	var out bytes.Buffer
	cmd.Stdout = &out
	err := cmd.Run()
	if err != nil {
		return "", err
	}
	return filepath.Base(strings.TrimSpace(out.String())), nil
}

func getCurrentBranchName() (string, error) {
	cmd := exec.Command("git", "rev-parse", "--abbrev-ref", "HEAD")
	var out bytes.Buffer
	cmd.Stdout = &out
	err := cmd.Run()
	if err != nil {
		return "", err
	}
	return strings.TrimSpace(out.String()), nil
}

func getStagedChangesDiff() (string, error) {
	cmd := exec.Command("git", "diff", "--staged")
	var out bytes.Buffer
	cmd.Stdout = &out
	err := cmd.Run()
	if err != nil {
		return "", err
	}
	return out.String(), nil
}

func formatDiffWithRepoAndBranchInfo(repoName, branchName, diff string) string {
	return fmt.Sprintf("%s/%s\n\n%s", repoName, branchName, diff)
}

func stageAllChanges() error {
	cmd := exec.Command("git", "add", "--all")
	return cmd.Run()
}

func prepareRequestPayload(diff, template, model, explanation string) ([]byte, error) {
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

func createAPIRequest(apiKey string, payloadBytes []byte) (*http.Request, error) {
	req, err := http.NewRequest("POST", OpenAIAPIURL, bytes.NewReader(payloadBytes))
	if err != nil {
		return nil, err
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+apiKey)

	return req, nil
}

func sendAPIRequest(req *http.Request) (*http.Response, error) {
	return http.DefaultClient.Do(req)
}

func readResponseBody(resp *http.Response) ([]byte, error) {
	return io.ReadAll(resp.Body)
}

func parseResponse(responseBody []byte) (string, string, error) {
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

func createCommit(commitMessage string) error {
	cmd := exec.Command("git", "commit", "-m", commitMessage)
	return cmd.Run()
}

func main() {
	app := &cli.App{
		Name:  "git-commit-helper",
		Usage: "Generate git commit messages using GPT-4",
		Flags: []cli.Flag{
			&cli.StringFlag{
				Name:    "explanation",
				Aliases: []string{"e"},
				Usage:   "Add a high level explanation of the commit",
			},
			&cli.BoolFlag{
				Name:    "commit",
				Aliases: []string{"c"},
				Usage:   "Commit the changes with the generated message",
			},
			&cli.StringFlag{
				Name:    "template",
				Aliases: []string{"t"},
				Value:   TEMPLATE_COMMIT,
				Usage:   "Specify a commit message template",
			},
			&cli.BoolFlag{
				Name:    "add",
				Aliases: []string{"a"},
				Usage:   "Stage all changes before generating the commit message",
			},
			&cli.StringFlag{
				Name:    "model",
				Aliases: []string{"m"},
				Value:   "gpt-4",
				Usage:   "Set the engine model to be used",
			},
		},
		Action: func(c *cli.Context) error {
			if OpenAI_API_KEY == "" {
				fmt.Println("Error: OPENAI_API_KEY environment variable not set")
				os.Exit(1)
			}

			if c.Bool("add") {
				err := stageAllChanges()
				if err != nil {
					fmt.Println("Error: Failed to stage all changes")
					os.Exit(1)
				}
			}

			diff, err := getStagedChangesDiff()
			if err != nil {
				fmt.Println("Error: Failed to get staged diff")
				os.Exit(1)
			}

			if diff == "" {
				fmt.Println("Warning: No staged changes found. Exiting.")
				os.Exit(0)
			}

			repoName, err := getRepositoryName()
			if err != nil {
				fmt.Println("Error: Failed to get repository name")
				os.Exit(1)
			}

			branchName, err := getCurrentBranchName()
			if err != nil {
				fmt.Println("Error: Failed to get current branch name")
				os.Exit(1)
			}

			formattedDiff := formatDiffWithRepoAndBranchInfo(repoName, branchName, diff)

			template := c.String("template")
			model := c.String("model")
			explanation := c.Args().Get(0)

			if explanation == "" {
				explanation = c.String("explanation")
			}

			payloadBytes, err := prepareRequestPayload(formattedDiff, template, model, explanation)

			if err != nil {
				fmt.Println("Error: Failed to prepare request payload")
				os.Exit(1)
			}

			req, err := createAPIRequest(OpenAI_API_KEY, payloadBytes)
			if err != nil {
				fmt.Println("Error: Failed to create API request")
				os.Exit(1)
			}

			resp, err := sendAPIRequest(req)
			if err != nil {
				fmt.Println("Error: Failed to send API request")
				os.Exit(1)
			}
			defer resp.Body.Close()

			if resp.StatusCode != http.StatusOK {
				fmt.Println("Error: Failed to generate commit message using open_ai api")
				os.Exit(1)
			}

			responseBody, err := readResponseBody(resp)
			if err != nil {
				fmt.Println("Error: Failed to read response body")
				os.Exit(1)
			}

			commitMessage, apiError, err := parseResponse(responseBody)
			if err != nil {
				fmt.Printf("Error: Failed to parse response: %v\n", err)
				os.Exit(1)
			}

			if apiError != "" {
				fmt.Printf("Error from OpenAI API: %s\n", apiError)
				os.Exit(1)
			}

			if c.Bool("commit") {
				err := createCommit(commitMessage)
				if err != nil {
					fmt.Println("Error: Failed to create commit")
					os.Exit(1)
				}
				fmt.Printf("Committed message: \n\n %s\n", commitMessage)
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
