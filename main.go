package main

import (
	"fmt"
	"os"

	"github.com/lguibr/comai/cli"
)

func main() {
	app := cli.GetApp()
	app.EnableBashCompletion = true

	err := app.Run(os.Args)
	if err != nil {
		fmt.Println(err)
		os.Exit(1)
	}
}
