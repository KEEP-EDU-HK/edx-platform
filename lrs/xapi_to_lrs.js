/** Import libraries **/
/**
* Installation:
* npm install --save fs
* npm install --save lazy
* npm install --save adl-xapiwrapper
* npm install --save config
*
*
* Configuration in different environment:
* Running the following command in production before running the code, the
* configuration will come form `config/production.json` instead of `config/default.json`
*
* e.g in production
* $ export NODE_ENV=production
**/

var fs   = require('fs');
var lazy = require('lazy');
var adl  = require('adl-xapiwrapper');
var config = require('config');

//// LRS Parameter from Config ////
var lrs_opts = {
    "url" : config.get('lrs.url'),
    "auth" : {
        "user" : config.get('lrs.auth.username'),
        "pass" : config.get('lrs.auth.password')
    }
};

var mylrs = new adl.XAPIWrapper(lrs_opts);


function parseQueue(line) {
    line = line.trim();

    // Do not process an empty line (this should not happen)
    if (line.length <= 2) return;

    mylrs.sendStatements(JSON.parse(line), function(err, resp, bdy) {
        if (!err) {
            if (resp.statusCode >= 200 && resp.statusCode < 300) {
                // Succeeded with HTTP returning status code 2xx; Leave
                return;
            } else {
                // Can reach LRS but the response is not what we expect
                console.error('Error: HTTP returned ' + resp.statusCode);
            }
        } else {
            // Error transferring an event to LRS
            console.error('Error: ' + err.message);
        }

        // Not returned at this point? Something is wrong!
        // Output the unsuccessful statement. Caller of this script should process it.
        console.log(line);
    });
}


/** main() **/

// Read queuing xAPI statements from file and transmit them to Learning Locker server
new lazy(fs.createReadStream(process.argv[2]))
    .lines
    .map(String)
    .map(parseQueue);

