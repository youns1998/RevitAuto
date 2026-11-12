using RevitAuto.Core;

var count = 0;
void Check(string label, Action check)
{
    check();
    count++;
    Console.WriteLine($"PASS {label}");
}
void Require(bool value) { if (!value) throw new Exception("Assertion failed."); }
void Reject(Action operation)
{
    try { operation(); }
    catch (FormatException) { return; }
    throw new Exception("Expected validation rejection.");
}
IReadOnlyList<SheetSpec> Read(string csv) => SheetPlans.ReadCsv(new StringReader(csv));

Check("Korean CSV and BOM", () => Require(Read("\uFEFFNumber,Name\r\nA101,1층 평면도")[0] == new SheetSpec("A101", "1층 평면도")));
Check("Quoted comma and escaped quote", () => Require(Read("Number,Name\nA101,\"평면, \"\"1층\"\"\"")[0].Name == "평면, \"1층\""));
Check("Whitespace normalization", () => Require(Read("Number,Name\n A101 , 평면도 ")[0] == new SheetSpec("A101", "평면도")));
Check("Wrong header", () => Reject(() => Read("번호,이름\nA101,평면도")));
Check("Empty input", () => Reject(() => Read("")));
Check("Header without sheets", () => Reject(() => Read("Number,Name\n")));
Check("Missing column", () => Reject(() => Read("Number,Name\nA101")));
Check("Extra column", () => Reject(() => Read("Number,Name\nA101,평면도,extra")));
Check("Empty number", () => Reject(() => Read("Number,Name\n,평면도")));
Check("Empty name", () => Reject(() => Read("Number,Name\nA101,  ")));
Check("Case-insensitive duplicate number", () => Reject(() => Read("Number,Name\nA101,평면\na101,입면")));
Check("Existing sheet collision before transaction", () => Reject(() => SheetPlans.Validate([new("A101", "평면")], ["a101"])));
Check("Multiline model name rejected", () => Reject(() => Read("Number,Name\nA101,\"평면\n입면\"")));
Check("Unclosed quote rejected", () => Reject(() => Read("Number,Name\nA101,\"평면")));
Check("View numbering skips occupied numbers", () => Require(SheetPlans.ForViews(["평면", "입면"], ["RA-001", "ra-003"]).Select(x => x.Number).SequenceEqual(["RA-002", "RA-004"])));
Check("CSV export round trip", () =>
{
    var sheets = new SheetSpec[] { new("A101", "1층 평면"), new("A102", "입면, \"남측\"") };
    using var output = new StringWriter();
    SheetPlans.WriteCsv(output, sheets);
    Require(Read(output.ToString()).SequenceEqual(sheets));
});
Check("Spreadsheet formulas escaped", () =>
{
    using var output = new StringWriter();
    SheetPlans.WriteCsv(output, [new("=1+1", " @SUM(1)")]);
    var parsed = Read(output.ToString())[0];
    Require(parsed.Number.StartsWith("'=") && parsed.Name.StartsWith("' @"));
});
Console.WriteLine($"Passed {count} checks.");
