var express     = require('express');
var app         = express();
var fs          = require('fs');
var utils       = require('./modules/utils');

app.use(express.static('public'));
app.set('views', './views');
app.set('view engine', 'jade');

app.get('/', function (req, res) {
    res.render('index');
});

app.get('/companies', function(req, res) {
    var q = req.query.q;
    var s = req.query.s || 0;

    if(q.length < 1) {
        return res.send({error: 'Too few characters in query.'});
    }

    var _q = q.toLowerCase();
    var _keys = _q.split(' ');
    
    var r = companies.filter(function(c) {
        for(var i = 0; i < _keys.length; i++) {
            if (_keys[i].length > 2 && c.n.toLowerCase().indexOf(_keys[i]) > -1) {                
                return true;
            }            
        }
        return false;  
    });


    if(s === 1) {
        r = r.map(function(c) {
            return c.n;
        });
    }

    r.sort(function(a,b) {
        var sa = utils.getKeywordMatchScore(a.n, _keys);
        var sb = utils.getKeywordMatchScore(b.n, _keys);

        if(sa > sb) {
            return -1;
        }
        else if(sa < sb) {
            return 1;
        }
        return 0;
    });

    res.send(r);
});

app.get('/profile', function(req, res) {
    var permalink = req.query.p;
    var retries = 4;
    var profileData;

    var profileFilePath = './comps/' + permalink + '.json';
    try {
        //Check if local copy of profile exists.
        var profileStats = fs.lstatSync(profileFilePath);
        profileData = fs.readFile(profileFilePath, 'utf8', function(err, data) {
            if(err) {
                return res.send({});
            }
            res.send(data);
        });
    }
    catch (e) {
        // If local copy of profile doesn't exist, get data using API.
        (function getData() {
            utils.getOrganizationData(permalink, function(data, resCode) {
                if(resCode !== 200 && --retries >= 0) {
                    return getData();
                }

                try{
                    var dataObject = JSON.parse(data);
                    profileData = utils.getOrganizationProfileFromData(dataObject);
                    fs.writeFile(profileFilePath, JSON.stringify(profileData), function(err) {});
                    res.send(profileData);   
                }
                catch(e) {
                    res.send({});
                    console.log('Error getting data (' + resCode + ')', data.split('\n').slice(0,3), e.stack);
                }
                
            });
        })();        
    }
});

console.log('Loading data...');
var server, companies;
if(!fs.existsSync('./comps')) {
    fs.mkdirSync('./comps');
}
fs.readFile('data/companies.json', function(err, data) {
    if(err) throw err;
    companies = JSON.parse(data);
    server = app.listen(3000, function () {
        var port = server.address().port;
        console.log('Listening at port', port);
    });
});