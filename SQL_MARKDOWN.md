/\*\*\*\*\*\* SSMS’ten SelectTopNRows komutu için betik  \*\*\*\*\*\*/

SELECT TOP (1000) \[id]

&#x20;     ,\[integration\_id]

&#x20;     ,\[schema\_text]

&#x20;     ,\[target\_table]

&#x20;     ,\[updated\_at]

&#x20; FROM \[ZehraTestDB].\[dbo].\[integration\_schemas]



/\*\*\*\*\*\* SSMS’ten SelectTopNRows komutu için betik  \*\*\*\*\*\*/

SELECT TOP (1000) \[id]

&#x20;     ,\[integration\_id]

&#x20;     ,\[qdrant\_point\_id]

&#x20;     ,\[chunk\_text]

&#x20; FROM \[ZehraTestDB].\[dbo].\[integration\_vectors]



/\*\*\*\*\*\* SSMS’ten SelectTopNRows komutu için betik  \*\*\*\*\*\*/

SELECT TOP (1000) \[id]

&#x20;     ,\[integration\_id]

&#x20;     ,\[param\_name]

&#x20;     ,\[param\_type]

&#x20;     ,\[is\_required]

&#x20;     ,\[default\_value]

&#x20;     ,\[description]

&#x20; FROM \[ZehraTestDB].\[dbo].\[integration\_params]



/\*\*\*\*\*\* SSMS’ten SelectTopNRows komutu için betik  \*\*\*\*\*\*/

SELECT TOP (1000) \[id]

&#x20;     ,\[name]

&#x20;     ,\[description]

&#x20;     ,\[wsdl\_url]

&#x20;     ,\[service\_method]

&#x20;     ,\[username]

&#x20;     ,\[password]

&#x20;     ,\[is\_active]

&#x20;     ,\[created\_at]

&#x20; FROM \[ZehraTestDB].\[dbo].\[integrations]

