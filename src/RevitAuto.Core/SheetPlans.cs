using System.Globalization;
using System.Text;
using Microsoft.VisualBasic.FileIO;

namespace RevitAuto.Core;

public sealed record SheetSpec(string Number, string Name);

public static class SheetPlans
{
    public static IReadOnlyList<SheetSpec> ReadCsv(TextReader input)
    {
        using var parser = new TextFieldParser(input)
        {
            TextFieldType = FieldType.Delimited,
            HasFieldsEnclosedInQuotes = true,
            TrimWhiteSpace = true
        };
        parser.SetDelimiters(",");
        try
        {
            var header = parser.ReadFields();
            if (header is not { Length: 2 }
                || !header[0].TrimStart('\uFEFF').Equals("Number", StringComparison.OrdinalIgnoreCase)
                || !header[1].Equals("Name", StringComparison.OrdinalIgnoreCase))
                throw new FormatException("CSV 첫 줄은 Number,Name이어야 합니다.");
            var result = new List<SheetSpec>();
            while (!parser.EndOfData)
            {
                var fields = parser.ReadFields();
                if (fields is not { Length: 2 })
                    throw new FormatException($"CSV {parser.LineNumber - 1}행: 번호와 이름 두 열이 필요합니다.");
                result.Add(new SheetSpec(fields[0].Trim(), fields[1].Trim()));
            }
            Validate(result, []);
            return result;
        }
        catch (MalformedLineException ex)
        {
            throw new FormatException($"CSV {ex.LineNumber}행의 따옴표 형식을 확인하세요.", ex);
        }
    }

    public static void Validate(IReadOnlyList<SheetSpec> sheets, IEnumerable<string> existingNumbers)
    {
        if (sheets.Count == 0) throw new FormatException("생성할 시트가 없습니다.");
        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var existing = new HashSet<string>(existingNumbers.Select(x => x.Trim()), StringComparer.OrdinalIgnoreCase);
        foreach (var sheet in sheets)
        {
            if (string.IsNullOrWhiteSpace(sheet.Number) || string.IsNullOrWhiteSpace(sheet.Name))
                throw new FormatException("시트 번호와 이름은 비워 둘 수 없습니다.");
            if (sheet.Number.Any(char.IsControl) || sheet.Name.Any(char.IsControl))
                throw new FormatException("시트 번호와 이름에 줄바꿈·제어 문자를 사용할 수 없습니다.");
            if (!seen.Add(sheet.Number.Trim())) throw new FormatException($"중복 시트 번호: {sheet.Number}");
            if (existing.Contains(sheet.Number.Trim())) throw new FormatException($"이미 존재하는 시트 번호: {sheet.Number}");
        }
    }

    public static IReadOnlyList<SheetSpec> ForViews(IEnumerable<string> viewNames, IEnumerable<string> existingNumbers)
    {
        var used = new HashSet<string>(existingNumbers, StringComparer.OrdinalIgnoreCase);
        var result = new List<SheetSpec>();
        var index = 1;
        foreach (var name in viewNames)
        {
            string number;
            do { number = "RA-" + (index++).ToString("D3", CultureInfo.InvariantCulture); }
            while (!used.Add(number));
            result.Add(new SheetSpec(number, name));
        }
        Validate(result, []);
        return result;
    }

    public static void WriteCsv(TextWriter output, IEnumerable<SheetSpec> sheets)
    {
        output.WriteLine("Number,Name");
        foreach (var sheet in sheets)
            output.WriteLine($"{Escape(sheet.Number)},{Escape(sheet.Name)}");
    }

    private static string Escape(string value)
    {
        // Prevent spreadsheet formula execution when an exported model name starts with =, +, - or @.
        if (value.TrimStart().FirstOrDefault() is '=' or '+' or '-' or '@') value = "'" + value;
        return "\"" + value.Replace("\"", "\"\"") + "\"";
    }
}
