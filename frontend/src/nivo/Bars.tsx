import { Box, Skeleton, Stack, useMantineTheme } from "@mantine/core";
import { ResponsiveBar } from "@nivo/bar";
import { useQuery } from "@tanstack/react-query";
import { AxiosError } from "axios";
import Placeholder from "../components/Placeholder";
import { getAxiosData, searchParams } from "../query";
import { NivoComponentProps, NivoRequest, NivoSkeletonProps, NivoTooltip, useNivoTheme } from "./Nivo";
import { useState, useEffect } from "react";
import { SunburstSkeleton } from "./Sunburst";
import { useElementSize } from "@mantine/hooks";

interface Datum {
    category: string
    color: string
    [key: string]: string | number
}

interface BarsData {
    data: Datum[]
    keys: string[]
    total: number
}

const useBarsData = (props: NivoRequest) =>
    useQuery<BarsData, AxiosError>({
        queryKey: ["categories", "changes", "bars", props],
        queryFn: () => getAxiosData(`/api/nivo/bars?${searchParams(props)}`)
    });

const BAR_HEIGHT = 55;

export const FinnanceBars = ({ request, size }: NivoComponentProps) => {
    const theme = useMantineTheme();
    const nivo = useNivoTheme();
    const query = useBarsData(request);

    const [data, setData] = useState<BarsData>()
    useEffect(() => query.data && setData(query.data), [query.data, setData])

    if (query.isError)
        return <Placeholder queries={[query]} height={3 * BAR_HEIGHT} />
    else if (data === undefined)
        return <SunburstSkeleton {...size} />

    const { data: bars, keys, total } = data;
    return <Box style={{ height: bars.length * (BAR_HEIGHT + 5) }}>
        <ResponsiveBar
            theme={nivo}
            data={bars} keys={keys}
            indexBy='category'
            layout='horizontal'
            colors={({ id, data }) => theme.fn.lighten(data[`${id}_color`].toString(), 0.15)}

            axisBottom={null}
            axisLeft={null}
            // borderColor={({ data: { id, data } }) => data['color']}
            borderColor={theme.colorScheme === 'light' ? theme.white : theme.colors.dark[7]}
            borderWidth={2}
            borderRadius={10}
            label={'id'}
            labelSkipWidth={64}
            labelTextColor={theme.colorScheme === 'light' ?
                theme.black : theme.white
            }
            enableGridY={false}
            tooltip={({ id, value }) =>
                <NivoTooltip label={id.toString()} value={value} currency_id={request.currency_id} perc={value / total * 100} />}
        />
    </Box>
}

export const BarsSkeleton = (props: NivoSkeletonProps) => {
    const { ref, width } = useElementSize();
    return <Stack spacing='xs'>
        <Skeleton height={BAR_HEIGHT} width={Math.random() * width} />
        <Skeleton height={BAR_HEIGHT} ref={ref}  />
        <Skeleton height={BAR_HEIGHT} width={Math.random() * width} />
    </Stack>
}
