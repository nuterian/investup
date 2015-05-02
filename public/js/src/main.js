var CompanyRow = React.createClass({
    render: function() {
        return (
                <li className="company-list-item row">
                	<div className="company-item-img col"><span className="company-item-img-hlp"></span><img src={this.props.company.i}/></div>
                	<div className="company-name col"><a href={'#' + this.props.company.p}>{this.props.company.n}</a></div>
                </li>
        );
    }
});

var CompanyList = React.createClass({
    render: function() {
        var rows = [],
        	to = Math.min(this.props.companies.length, 10);
        for( var i = 0; i < to; i++) {
        	var company = this.props.companies[i];
        	rows.push(<CompanyRow company={company} />);
        }
        return (
        	<ul className="company-list">
        		{rows}
        	</ul>
        );
    }
});

var SearchBar = React.createClass({
	handleKeyDown: function() {
		var query = React.findDOMNode(this.refs.search).value.trim();
		this.props.onQuery(query);
	},

    componentWillMount: function() {
    	this.handleKeyDown = _.debounce(this.handleKeyDown, 300);
    },

    render: function() {
        return (
            <input type="text" placeholder="Search by company name..." className="sb" onKeyDown={this.handleKeyDown} ref="search" />
        );
    }
});


var FilterableCompanyList = React.createClass({
	getInitialState: function() {
		return {
			companies: []
		}
	},

	loadCompaniesFromServer: function(q) {
		var queryUrl =  this.props.url + q;
	    $.ajax({
	      	url: queryUrl,
	      	dataType: 'json',
	      	success: function(data) {
	        	this.setState({companies: data});
	      	}.bind(this),
	      	error: function(xhr, status, err) {
	        	console.error(queryUrl, status, err.toString());
	      	}.bind(this)
	    });		
	},

	handleOnQuery: function(q) {
		if(q.length < 2) {
			this.setState({companies: []});
		}
		else {
			this.loadCompaniesFromServer(q);
		}
	},

    render: function() {
        return (
        	<div>
	            <div className="header row">
	            	<h1 className="logo col">Investup</h1>
	                <SearchBar
	                	className="col"
	                	onQuery={this.handleOnQuery}
	                />
	            </div>
	            <div className="list-wrapper">
		            <CompanyList
		            	companies={this.state.companies}
		            />
		        </div>
	        </div>
            
        );
    }
});

React.render(<FilterableCompanyList url="/companies?q=" />, document.body);